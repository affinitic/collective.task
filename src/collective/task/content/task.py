from zope.interface import implements

from plone.dexterity.content import Container
from plone import api

from collective.task.interfaces import IBaseTask, IDeadline


class ITask(IBaseTask, IDeadline):
    """Schema for task"""
    pass


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
