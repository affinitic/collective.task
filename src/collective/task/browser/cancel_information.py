
import z3c.form
from Products.CMFCore.utils import getToolByName
from collective.task import _
from plone import api
from plone.supermodel import model
from z3c.form import button
from z3c.form.browser.checkbox import CheckBoxFieldWidget
from z3c.form.field import Fields
from z3c.form.interfaces import HIDDEN_MODE
from zope import schema
from zope.annotation.interfaces import IAnnotations
from zope.i18nmessageid import MessageFactory
from zope.interface import directlyProvides
from zope.interface import implements
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary
from DateTime import DateTime

PMF = MessageFactory('plone')


def responsibles_vocabulary(context):
    acl_users = getToolByName(context, 'acl_users')
    terms = []
    informations = context.listFolderContents(contentFilter={"portal_type": "information"})

    for information in informations:
        responsible_id = information.responsible[0]
        user = acl_users.getUserById(responsible_id)
        responsible_name = user.getProperty('fullname') or responsible_id
        terms.append(SimpleVocabulary.createTerm(responsible_id, str(responsible_id), responsible_name))

    return SimpleVocabulary(terms)


directlyProvides(responsibles_vocabulary, IContextSourceBinder)


class IInformationRecipients(model.Schema):
    """"""
    responsible = schema.List(
        value_type=schema.Choice(
            source=responsibles_vocabulary,
        ),
    )


class CancelInformation(z3c.form.form.Form):
    """Cancel (delete) one or more information
    """

    implements(z3c.form.interfaces.IFieldsForm)
    fields = Fields(IInformationRecipients)
    fields["responsible"].widgetFactory = CheckBoxFieldWidget

    label = _(u'Cancel information(s)')
    description = _(u'Please select information notices to cancel. The responsibles will be notified by mail.')
    ignoreContext = True

    @button.buttonAndHandler(_('Apply'), name='apply')
    def handleApply(self, action):
        data, errors = self.extractData()
        responsibles = data.get('responsible')
        if not responsibles:
            return

        informations = self.context.listFolderContents(contentFilter={
            'portal_type': 'information',
            'Creator': api.user.get_current().id,
        })

        for information in informations:
            responsible_id = information.responsible[0]
            if responsible_id in responsibles:
                local_roles = self.context.get_local_roles_for_userid(responsible_id)
                leftover_roles = set(local_roles).difference(['Editor'])
                if leftover_roles:
                    # set leftover roles
                    self.context.manage_setLocalRoles(responsible_id, leftover_roles)
                else:
                    # delete local roles for user
                    self.context.manage_delLocalRoles([responsible_id])
                self.context.reindexObjectSecurity()

                # store history about this task on its document
                annotations = IAnnotations(self.context)
                if not 'pfwbged_history' in annotations:
                    annotations['pfwbged_history'] = []
                # first, the information creation
                annotations['pfwbged_history'].append({
                    'time': information.creation_date,
                    'action_id': 'creation',
                    'action': 'Creation',
                    'actor_name': information.creators[0],
                    'task_title': information.title,
                })
                # second, the information deletion
                annotations['pfwbged_history'].append({
                    'time': DateTime(),
                    'action_id': 'cancellation',
                    'action': 'Cancellation',
                    'actor_name': api.user.get_current().getId(),
                    'task_title': information.title,
                    'responsible': information.responsible[0],
                })
                # assign it back as a change to the list won't trigger the
                # annotation to be saved on disk.
                annotations['pfwbged_history'] = annotations['pfwbged_history'][:]

                # remove information (responsible is notified by email with an Event)
                self.context.manage_delObjects(information.id)

        self.request.response.redirect(self.context.absolute_url())
