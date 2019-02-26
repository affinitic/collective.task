
import z3c.form
from Products.CMFCore.utils import getToolByName
from collective.task import _
from pfwbged.policy.subscribers.document import email_notification_of_canceled_information
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

                # remove information (responsible is notified by email with an Event)
                self.context.manage_delObjects(information.id)

        self.request.response.redirect(self.context.absolute_url())
