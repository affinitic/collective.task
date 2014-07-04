# -*- coding: utf-8 -*-
"""Module where all interfaces, events and exceptions live."""
import datetime

from zope import schema
from zope.interface import provider

from Products.CMFPlone.utils import base_hasattr

from plone.autoform import directives as form
from plone.directives.form.value import default_value
from plone.supermodel import model
from plone.theme.interfaces import IDefaultPloneLayer
from plone.formwidget.datetime.z3cform.widget import DatetimeFieldWidget

from collective.z3cform.rolefield.field import LocalRolesToPrincipals
from collective.dms.basecontent.widget import AjaxChosenMultiFieldWidget

from collective.task import _


class ICollectiveTaskLayer(IDefaultPloneLayer):
    """Marker interface that defines a Zope 3 browser layer."""


@provider(schema.interfaces.IContextAwareDefaultFactory)
def deadlineDefaultValue(context):
    """Default value for deadline field, copy deadline of the parent (context),
    or set it to today+3 days at 12:00"""
    if base_hasattr(context, 'deadline'):
        return context.deadline

    date = datetime.datetime.today() + datetime.timedelta(days=3)
    hour = datetime.time(12, 0)
    return datetime.datetime.combine(date, hour)


class IBaseTask(model.Schema):
    """Interface for all "tasks" content types"""
    title = schema.TextLine(title=_(u'Title'))
    note = schema.Text(title=_(u'Note'),
                       required=False)

    enquirer = LocalRolesToPrincipals(
        title=_(u"Enquirer"),
        roles_to_assign=('Reviewer',),
        value_type=schema.Choice(
            vocabulary="dms.principals"
        ),
        min_length=0,
        max_length=1,
        required=False,
    )
    form.widget(enquirer=AjaxChosenMultiFieldWidget)
    form.mode(enquirer='hidden')

    responsible = LocalRolesToPrincipals(
        title=_(u"Addressee"),
        roles_to_assign=('Editor',),
        value_type=schema.Choice(
            vocabulary="dms.principals"
        ),
        min_length=1,
        max_length=1,
        required=True,
    )
    form.widget(responsible=AjaxChosenMultiFieldWidget)

    form.order_after(note='responsible')


class IDeadline(model.Schema):
    deadline = schema.Datetime(title=_(u'Deadline'),
                               defaultFactory=deadlineDefaultValue,
                               required=False)
    form.widget(deadline=DatetimeFieldWidget)


@default_value(field=IDeadline['deadline'])
def deadlineDefaultValue(data):
    """Default value for deadline field today+3 days at 18:00"""
    date = datetime.datetime.today() + datetime.timedelta(days=3)
    hour = datetime.time(18, 0)
    return datetime.datetime.combine(date, hour)
