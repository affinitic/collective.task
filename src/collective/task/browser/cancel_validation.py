# -*- coding: utf-8 -*-

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
from zope.i18nmessageid import MessageFactory
from zope.interface import directlyProvides
from zope.interface import implements
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary

from zope.component import getUtility
from zope.intid.interfaces import IIntIds
from zc.relation.interfaces import ICatalog
from collective.task.content.validation import IValidation

PMF = MessageFactory('plone')


def validations_vocabulary(context):
    acl_users = getToolByName(context, 'acl_users')
    terms = []
    catalog = api.portal.get_tool('portal_catalog')
    container_path = '/'.join(context.getPhysicalPath())
    validations = catalog.searchResults({
        'path': container_path,
        'portal_type': 'validation',
        'review_state': 'todo',
        'Creator': api.user.get_current().id,
    })

    for brain in validations:
        validation = brain.getObject()
        terms.append(SimpleVocabulary.createTerm(validation.id, str(validation.id), validation.title))

    return SimpleVocabulary(terms)


directlyProvides(validations_vocabulary, IContextSourceBinder)


class IValidations(model.Schema):
    """"""
    validations = schema.List(
        value_type=schema.Choice(
            source=validations_vocabulary,
        ),
    )


class CancelValidationRequest(z3c.form.form.Form):
    """Cancel (delete) one or more validation requests
    """

    implements(z3c.form.interfaces.IFieldsForm)
    fields = Fields(IValidations)
    fields["validations"].widgetFactory = CheckBoxFieldWidget

    label = _(u'Cancel validations request(s)')
    description = _(u'Please select validation requests to cancel. The responsibles will be notified by mail.')
    ignoreContext = True

    @button.buttonAndHandler(_('Apply'), name='apply')
    def handleApply(self, action):
        data, errors = self.extractData()
        validations = data.get('validations')
        if not validations:
            return

        refs_catalog = getUtility(ICatalog)
        intids = getUtility(IIntIds)
        workflow = api.portal.get_tool('portal_workflow')

        for validation_id in validations:
            validation = self.context.get(validation_id)
            if not validation:
                continue

            # find version linked to the validation
            validation_intid = intids.getId(validation)
            relations = list(refs_catalog.findRelations({
                'from_id': validation_intid,
                'from_interfaces_flattened': IValidation,
            }))
            if not relations:
                continue
            version = relations[0].to_object

            self.context.manage_delObjects(validation.id)

            # return the version to its previous state, if possible
            with api.env.adopt_user('admin'):
                review_history = workflow.getInfoFor(version, 'review_history')
            if len(review_history) >= 2 and review_history[-1]['review_state'] == 'pending':
                return_state = review_history[-2]['review_state']
                api.content.transition(obj=version,
                                       transition='back_to_{}'.format(return_state))
                version.reindexObject(idxs=['review_state'])

        self.request.response.redirect(self.context.absolute_url())
