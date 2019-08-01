import uuid
from copy import deepcopy
from datetime import datetime
from flask_sqlalchemy import BaseQuery
from sqlalchemy import or_
from sqlalchemy.orm.base import _entity_descriptor
from opsy.flask_extensions import db
from opsy.exceptions import DuplicateError
from opsy.utils import merge_dict

###############################################################################
# Base models
###############################################################################


class TimeStampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow())
    updated_at = db.Column(db.DateTime, default=datetime.utcnow(),
                           onupdate=datetime.utcnow())


class OpsyQuery(BaseQuery):

    def filter_in(self, ignore_none=False, **kwargs):
        filters = []
        for key, value in kwargs.items():
            local_descriptor = None  # for joins this is the local attribute
            if '___' in key:
                key, relationship_attr = key.split('___', 1)
            else:
                relationship_attr = None
            descriptor = _entity_descriptor(self._joinpoint_zero(), key)
            if relationship_attr:
                self = self.join(descriptor, isouter=True)
                local_descriptor = descriptor
                descriptor = _entity_descriptor(descriptor, relationship_attr)
            if isinstance(value, str):
                filters.extend(self._get_filters_list(
                    descriptor, value, local_descriptor))
            else:
                filters.append(descriptor == value)
        return self.filter(*filters)

    def _get_filters_list(self, descriptor, items, local_descriptor):

        filters_list = []
        if items:
            include, exclude, like, not_like = self._parse_filters(items)
            include_list = []
            exclude_list = []
            if include:
                include_list.append(descriptor.in_(include))
            if like:
                include_list.extend([descriptor.like(x) for x in like])
            if include_list:
                filters_list.append(or_(*include_list))
            if exclude:
                exclude_list.append(descriptor.in_(exclude))
            if not_like:
                exclude_list.extend([descriptor.like(x) for x in not_like])
            if exclude_list:
                if local_descriptor:
                    # If this is a join we want to also include things that
                    # don't match the join condition on negation. So like
                    # if the foreign key is null, for example.
                    filters_list.append(
                        ~local_descriptor.any(or_(*exclude_list)))
                else:
                    filters_list.append(~or_(*exclude_list))
        return filters_list

    def _parse_filters(self, items):
        if items:
            item_list = items.split(',')
            # Wrap in a set to remove duplicates
            include = list({x for x in item_list
                            if not x.startswith('!') and '*' not in x})
            exclude = list({x[1:] for x in item_list
                            if x.startswith('!') and '*' not in x})
            like = list({x.replace('*', '%') for x in item_list
                         if not x.startswith('!') and '*' in x})
            not_like = list({x[1:].replace('*', '%') for x in item_list
                             if x.startswith('!') and '*' in x})
        else:
            include, exclude, like, not_like = [], [], [], []
        return include, exclude, like, not_like

    def get_or_fail(self, ident):
        obj = self.get(ident)
        if obj is None:
            raise ValueError
        return obj

    def first_or_fail(self):
        obj = self.first()
        if obj is None:
            raise ValueError
        return obj


class BaseModel:

    query_class = OpsyQuery

    id = db.Column(db.String(36),  # pylint: disable=invalid-name
                   default=lambda: str(uuid.uuid4()), primary_key=True)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def create(cls, **kwargs):
        obj = cls(**kwargs)
        return obj.save()

    @classmethod
    def get_by_id(cls, obj_id, **kwargs):
        return cls.query.get_or_fail(obj_id)

    @classmethod
    def delete_by_id(cls, obj_id, **kwargs):
        return cls.query.get_or_fail(obj_id).delete(**kwargs)

    @classmethod
    def update_by_id(cls, obj_id, **kwargs):
        return cls.query.get_or_fail(obj_id).update(**kwargs)

    def update(self, commit=True, **kwargs):
        kwargs.pop('id', None)
        for key, value in kwargs.items():
            if isinstance(value, dict) and value.pop('__update', False):
                merge_lists = value.pop('__merge_lists', False)
                value = merge_dict(
                    getattr(self, key), value, merge_lists=merge_lists)
            setattr(self, key, value)
        return self.save() if commit else self

    def save(self):
        db.session.add(self)
        db.session.commit()
        return self

    def delete(self, commit=True):
        db.session.delete(self)
        if commit:
            db.session.commit()

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, self.id)


class NamedModel(BaseModel):

    name = db.Column(db.String(128), unique=True, index=True, nullable=False)

    def __init__(self, name, **kwargs):
        self.name = name
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def create(cls, name, *args, obj_class=None, **kwargs):
        if cls.query.filter_by(name=name).first():
            raise DuplicateError('%s already exists with name "%s".' % (
                cls.__name__, name))
        if obj_class:
            obj = obj_class(name, *args, **kwargs)
        else:
            obj = cls(name, *args, **kwargs)
        return obj.save()

    @classmethod
    def delete_by_name(cls, obj_name, **kwargs):
        return cls.query.filter_by(name=obj_name).first_or_fail().delete(
            **kwargs)

    @classmethod
    def update_by_name(cls, obj_name, **kwargs):
        return cls.query.filter_by(name=obj_name).first_or_fail().update(
            **kwargs)

    @classmethod
    def get_by_id_or_name(cls, obj_id_or_name, error_on_none=False):
        obj = cls.query.filter(db.or_(
            cls.name == obj_id_or_name, cls.id == obj_id_or_name)).first()
        if not obj and error_on_none:
            raise ValueError('No %s found with name or id "%s".' %
                             (cls.__name__, obj_id_or_name))
        return obj

    @classmethod
    def delete_by_id_or_name(cls, obj_id_or_name, error_on_none=True,
                             **kwargs):
        return cls.get_by_id_or_name(
            obj_id_or_name, error_on_none=error_on_none).delete(**kwargs)

    @classmethod
    def update_by_id_or_name(cls, obj_id_or_name, error_on_none=True,
                             **kwargs):
        return cls.get_by_id_or_name(
            obj_id_or_name, error_on_none=error_on_none).update(**kwargs)

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, self.name)
