from zope.interface import implements
from zope import schema

from plone.autoform import directives as form
from plone.dexterity.content import Container
from plone import api

from collective.z3cform.rolefield.field import LocalRolesToPrincipals
from collective.dms.basecontent.widget import AjaxChosenMultiFieldWidget

from collective.task import _
from collective.task.interfaces import IBaseTask, IDeadline


class ITask(IBaseTask, IDeadline):
    """Schema for task"""

    responsible = LocalRolesToPrincipals(
        title=_(u"Addressees"),
        roles_to_assign=('Editor',),
        value_type=schema.Choice(
            vocabulary="dms.principals"
        ),
        min_length=1,
        required=True,
    )
    form.widget(responsible=AjaxChosenMultiFieldWidget)


class Task(Container):
    """Task content type"""
    implements(ITask)

    meta_type = 'task'
    # disable local roles inheritance
    __ac_local_roles_block__ = True

    def get_subtask_states(self):
        subtasks = self.listFolderContents()
        return [api.content.get_state(subtask) for subtask in subtasks]

    def subtasks_abandoned(self):
        return set(['abandoned']) == set(self.get_subtask_states())

    def subtasks_done(self):
        return set(['done']) == set(self.get_subtask_states())
