
import z3c.form
from Products.CMFCore.utils import getToolByName
from attribute_task import find_nontask
from collective.task import _
from pfwbged.policy.subscribers.document import email_notification_of_canceled_subtask
from plone import api
from plone.supermodel import model
from z3c.form import button
from z3c.form.browser.checkbox import CheckBoxFieldWidget
from z3c.form.field import Fields
from z3c.form.interfaces import HIDDEN_MODE
from zope import schema
from zope.i18nmessageid import MessageFactory
from zope.interface import directlyProvides
from zope.interface import implements
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary

PMF = MessageFactory('plone')


def get_principal(principal_id):
    principal = api.user.get(principal_id)
    if not principal:
        principal = api.group.get(principal_id)
    return principal


def responsibles_vocabulary(context):
    acl_users = getToolByName(context, 'acl_users')
    terms = []

    subtasks = context.listFolderContents()
    responsible_ids = [subtask.responsible[0] for subtask in subtasks]

    for responsible_id in responsible_ids:
        group = acl_users.getGroupById(responsible_id)
        user = acl_users.getUserById(responsible_id)
        if group:
            responsible_name = group.getProperty('title')
        elif user:
            responsible_name = user.getProperty('fullname')
        else:
            responsible_name = responsible_id
        terms.append(SimpleVocabulary.createTerm(responsible_id, str(responsible_id), responsible_name))

    return SimpleVocabulary(terms)


directlyProvides(responsibles_vocabulary, IContextSourceBinder)


class ITaskRecipients(model.Schema):
    """"""
    responsible = schema.List(
        value_type=schema.Choice(
            source=responsibles_vocabulary,
        ),
    )


class CancelTaskAttribution(z3c.form.form.Form):
    """Cancel (delete) one or more subtasks
    """

    implements(z3c.form.interfaces.IFieldsForm)
    fields = Fields(ITaskRecipients)
    fields["responsible"].widgetFactory = CheckBoxFieldWidget

    label = _(u'Cancel attribution(s)')
    description = _(u'Please select attributions to cancel. The responsibles will be notified by mail.')
    ignoreContext = True


    @button.buttonAndHandler(_('Apply'), name='apply')
    def handleApply(self, action):
        data, errors = self.extractData()
        responsibles = data.get('responsible')
        if not responsibles:
            return
        for subtask in self.context.listFolderContents():
            responsible = subtask.responsible[0]
            if responsible in responsibles:

                # remove Editor on document
                document = find_nontask(subtask)
                local_roles = document.get_local_roles_for_userid(responsible)
                leftover_roles = set(local_roles).difference(['Editor'])
                if leftover_roles:
                    # set leftover roles
                    document.manage_setLocalRoles(responsible, leftover_roles)
                else:
                    # delete local roles for user
                    document.manage_delLocalRoles([responsible])
                document.reindexObjectSecurity()

                # remove relevant subtask (responsibles are notified by email with an Event)
                self.context.manage_delObjects(subtask.id)

        self.request.response.redirect(find_nontask(self.context).absolute_url())
