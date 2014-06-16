from copy import deepcopy

from z3c.form import button
from z3c.form.field import Fields
from z3c.form.interfaces import HIDDEN_MODE
from zope import schema

from Acquisition import aq_inner, aq_chain

from zope.i18nmessageid import MessageFactory
from plone.dexterity.browser.add import DefaultAddForm
from plone.dexterity.i18n import MessageFactory as DMF
from plone.supermodel import model

from Products.CMFPlone.utils import base_hasattr
from Products.statusmessages.interfaces import IStatusMessage

from collective.task import _

PMF = MessageFactory('plone')


def find_nontask(obj):
    """Find the first non task object in acquisition chain"""
    for item in aq_chain(aq_inner(obj)):
        if base_hasattr(item, 'portal_type'):
            if item.portal_type != 'task':
                return item
        else:
            return item


class IWorkflowAction(model.Schema):
    """Simple schema that contains workflow action hidden field"""
    workflow_action = schema.TextLine(title=_(u'Workflow action'),
                                      required=False
                                      )


class AttributeTask(DefaultAddForm):
    """When an "Attribute" transition is triggered,
    create a new subtask
    """
    label = PMF(u"Attribute task to")
    description = u""
    portal_type = 'task'

    def updateFields(self):
        super(AttributeTask, self).updateFields()
        self.fields += Fields(IWorkflowAction)
        self.fields['workflow_action'].mode = HIDDEN_MODE

    def updateWidgets(self):
        """Update widgets then add workflow_action value to workflow_action field"""
        super(AttributeTask, self).updateWidgets()
        if 'workflow_action' in self.request:
            self.widgets['workflow_action'].value = (
                self.request['workflow_action'])
        self.widgets['title'].value = self.context.title

    @button.buttonAndHandler(_('Add'), name='save')
    def handleAdd(self, action):
        """When the subtask is added,
        grant Reviewer role to current user on new object
        Then, execute transition on container
        """
        parent_task = aq_inner(self.context)
        container_url = parent_task.absolute_url()
        data, errors = self.extractData()
        workflow_action = data['workflow_action']
        del data['workflow_action']
        if errors:
            self.status = self.formErrorsMessage
            return
        obj = None
        for responsible in data['responsible']:
            _data = deepcopy(data)
            _data['responsible'] = [responsible]
            obj = self.createAndAdd(_data)
        if obj is not None:
            # mark only as finished if we get the new object
            self._finishedAdd = True
            IStatusMessage(self.request).addStatusMessage(DMF(u"Item created"), "info")
            # set Editor role to task responsible on the first non Task object in acquisition
            nontask = find_nontask(parent_task)
            for responsible in data['responsible']:
                nontask.manage_addLocalRoles(responsible, ['Editor',])
            nontask.reindexObjectSecurity()
            self.immediate_view = "%s/content_status_modify?workflow_action=%s" % (container_url, workflow_action)
