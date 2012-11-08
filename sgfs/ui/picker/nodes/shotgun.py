import functools

from PyQt4 import QtCore, QtGui
Qt = QtCore.Qt

from ..utils import debug
from .base import Node


class ShotgunQuery(Node):
    
    backrefs = {
        'Asset': [('Project', 'project')],
        'HumanUser': [None],
        'Project': [None],
        'PublishEvent': [('Task', 'sg_link')],
        'Sequence': [('Project', 'project')],
        'Shot': [('Sequence', 'sg_sequence')],
        'Task': [('Shot', 'entity'), ('Asset', 'entity')],
        'Ticket': [('Tool', 'sg_tool')],
        'Tool': [('Project', 'project')],
    }
    
    formats = {
        'Project': ['{Project[name]}'],
        'HumanUser': ['{HumanUser[email]}'],
        'Sequence': ['{Sequence[code]}'],
        'Asset': ['{Asset[sg_asset_type]}', '{Asset[code]}'],
        'Shot': ['{Shot[code]}'],
        'Task': ['{Task[step][code]}', '{Task[content]}'],
        'PublishEvent': ['{PublishEvent[sg_type]}', '{PublishEvent[code]}', 'v{PublishEvent[sg_version]:04d}'],
        'Tool': ['{Tool[code]}'],
        'Ticket': ['{Ticket[title]}'],
    }
    
    icons = {
        'Sequence': '/home/mboers/Documents/icons/fatcow/16x16/film_link.png',
        'Shot': '/home/mboers/Documents/icons/fatcow/16x16/film.png',
        'Task': '/home/mboers/Documents/icons/fatcow/16x16/to_do_list.png',
        'PublishEvent': '/home/mboers/Documents/icons/fatcow/16x16/brick.png',
        'Asset': '/home/mboers/Documents/icons/fatcow/16x16/box_closed.png',
    }
    
    fields = {
        'Task': ['step.Step.color'],
        'Tool': ['code'],
        'Ticket': ['title'],
        'HumanUser': ['firstname', 'lastname', 'email'],
    }
    
    @classmethod
    def specialize(cls, entity_types, **kwargs):
        return functools.partial(cls,
            entity_types=entity_types,
            **kwargs
        )
    
    def __init__(self, *args, **kwargs):
        self.entity_types = kwargs.pop('entity_types')
        super(ShotgunQuery, self).__init__(*args, **kwargs)
    
    def __repr__(self):
        return '<%s for %r at 0x%x>' % (self.__class__.__name__, self.active_types, id(self))
    
    def is_next_node(self, state):
        
        # If any types have a backref that isn't satisfied.
        self.active_types = []
        for type_ in self.entity_types:
            for backref in self.backrefs[type_]:
                if backref is None or backref[0] == state.get('self', {}).get('type'):
                    self.active_types.append(type_)
                    continue
        
        return bool(self.active_types)
    
    def child_matches_initial_state(self, child, init_state):
        
        last_entity = child.state.get('self')
        
        if not last_entity:
            return
        
        if last_entity['type'] not in self.active_types:
            return
        
        return last_entity == init_state.get(last_entity['type'])
    
    def update(self, *args):
        super(ShotgunQuery, self).update(*args)
        self.view_data['header'] = self.view_data[Qt.DisplayRole]
    
    def get_initial_children(self, init_state):
        for type_ in self.active_types:
            # yield Group(model,
            #     ('group', type_),
            #     {
            #         Qt.DisplayRole: entity['type'] + 's',
            #         Qt.DecorationRole: self.icons.get(entity['type']),
            #     },
            #     {}
            # )
            if type_ in init_state:
                entity = init_state[type_]
                yield self._child_tuple_from_entity(entity)
    
    def _child_tuple_from_entity(self, entity):
        
        labels = []
        for format_ in self.formats[entity['type']]:
            state = dict(self.state)
            state[entity['type']] = entity
            try:
                labels.append(format_.format(**state))
            except KeyError:
                labels.append('%r %% %r' % (format_, entity))
        
        groups = []
        if len(self.active_types) > 1:
            groups.append((
                ('group', entity['type']),
                {
                    Qt.DisplayRole: entity['type'] + 's',
                    Qt.DecorationRole: self.icons.get(entity['type']),
                },
                {
                    'entity_type': entity['type'],
                }
            ))
        
        for i, label in enumerate(labels[:-1]):
            groups.append((
                ('group', entity['type'], label),
                {
                    Qt.DisplayRole: label
                }, {
                    '%s.groups[%d]' % (entity['type'], i): label
                }
            ))
        
        view_data = {
            Qt.DisplayRole: labels[-1],
            'groups': groups,
            'header': labels[-1]
        }
        
        if entity.get('step') and entity['step'].get('color'):
            color = QtGui.QColor.fromRgb(*(int(x) for x in entity['step']['color'].split(',')))
            for group in groups:
                group[1][Qt.DecorationRole] = color
            view_data[Qt.DecorationRole] = color
            
        if entity['type'] in self.icons:
            view_data[Qt.DecorationRole] = self.icons[entity['type']]
        
        new_state = {
            entity['type']: entity,
            'self': entity,
        }
        
        return entity.cache_key, view_data, new_state
    
    def fetch_async_children(self, type_i=0):
        
        if type_i + 1 < len(self.active_types):
            self.schedule_async_fetch(self.fetch_async_children, type_i + 1)
        
        type_ = self.active_types[type_i]
        
        filters = []
        for backref in self.backrefs[type_]:
            if backref and backref[0] in self.state:
                filters.append((backref[1], 'is', self.state[backref[0]]))
        
        res = []
        for entity in self.model.sgfs.session.find(type_, filters, self.fields.get(type_) or []):
            res.append(self._child_tuple_from_entity(entity))
        
        # Sort by label.
        res.sort(key=lambda x: x[1][Qt.DisplayRole])
        
        return res