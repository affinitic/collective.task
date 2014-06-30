import inspect
from logging import getLogger

from Acquisition import aq_parent
from five import grok

from OFS.interfaces import IObjectWillBeRemovedEvent
from zope.lifecycleevent.interfaces import IObjectAddedEvent, IObjectModifiedEvent
from zope.container.contained import ContainerModifiedEvent

from plone import api
from Products.DCWorkflow.interfaces import IAfterTransitionEvent

from collective.z3cform.rolefield.field import LocalRolesToPrincipalsDataManager

from collective.task.behaviors import ITarget
from collective.task.content.task import ITask
from collective.task.content.opinion import IOpinion
from collective.task.content.validation import IValidation
from collective.task.interfaces import IBaseTask
from collective.dms.basecontent.dmsdocument import IDmsDocument

log = getLogger(__name__)


def grant_local_role_to_responsible(context, role, target):
    """Grant local role to responsible on target"""
    for responsible in context.responsible:
        target.manage_addLocalRoles(responsible, [role])
    target.reindexObject()


@grok.subscribe(ITask, IAfterTransitionEvent)
def task_changed_state(context, event):
    """When a task is abandoned or done, check if it is a subtask
    and make the wanted transition to parent
    """
    log.info(inspect.stack()[0][3])
    parent = context.getParentNode()
    if parent.portal_type == 'task':
        with api.env.adopt_roles(['Reviewer']):
            if event.new_state.id == 'done':
                with api.env.adopt_user('admin'):
                    try:
                        api.content.transition(obj=parent, transition='subtask-done')
                    except api.exc.InvalidParameterError:
                        pass
                parent.reindexObject(idxs=['review_state'])
            elif event.new_state.id == 'abandoned':
                with api.env.adopt_user('admin'):
                    try:
                        api.content.transition(obj=parent, transition='subtask-abandoned')
                    except api.exc.InvalidParameterError:
                        pass
                parent.reindexObject(idxs=['review_state'])


@grok.subscribe(ITask, IObjectWillBeRemovedEvent)
def reopen_parent_task(context, event):
    """When a task is deleted, reopen its parent task
    """
    log.info(inspect.stack()[0][3])
    parent = context.getParentNode()
    parent_state = api.content.get_state(parent)
    if parent.portal_type == 'task' and parent_state == 'attributed':
        state = api.content.get_state(context)
        if state == 'todo':
            with api.env.adopt_roles(['Reviewer']):
                api.content.transition(obj=context, transition='abandon')
                context.reindexObject(idxs=['review_state'])
        elif state == 'refusal-requested':
            with api.env.adopt_roles(['Reviewer']):
                api.content.transition(obj=context, transition='accept-refusal')
                context.reindexObject(idxs=['review_state'])
        elif state == 'in-progress':
            with api.env.adopt_roles(['Editor']):
                api.content.transition(obj=context, transition='ask-for-refusal')
                context.reindexObject(idxs=['review_state'])
            with api.env.adopt_roles(['Reviewer']):
                api.content.transition(obj=context, transition='accept-refusal')
                context.reindexObject(idxs=['review_state'])


@grok.subscribe(IBaseTask, IObjectAddedEvent)
def set_enquirer(context, event):
    """Set Enquirer field after task creation"""
    log.info(inspect.stack()[0][3])
    enquirer = api.user.get_current().id
    enquirer_dm = LocalRolesToPrincipalsDataManager(context, IBaseTask['enquirer'])
    enquirer_dm.set((enquirer,))

    parent = aq_parent(context)
    if IBaseTask.providedBy(parent):
        # parent is also a task, we create Reader local role value on its own
        # roles, unless parent enquirer is the greffier.
        if not 'Greffier' in api.user.get_roles(parent.enquirer[0]):
            for user_id, roles in parent.get_local_roles():
                if 'Reader' in roles or 'Reviewer' in roles:
                    context.manage_addLocalRoles(user_id, ['Reader'])

    context.reindexObjectSecurity()
    context.reindexObject(idxs=['allowedRolesAndUsers'])


@grok.subscribe(ITarget, IObjectAddedEvent)
def set_reader_on_target(context, event):
    """Set Reader role on target to responsible after opinion or validation creation"""
    log.info(inspect.stack()[0][3])
    if context.target:
        target = context.target.to_object
        grant_local_role_to_responsible(context, 'Reader', target)


@grok.subscribe(IValidation, IObjectAddedEvent)
def set_reviewer_on_target(context, event):
    """Set Reviewer role on target to responsible after validation creation"""
    log.info(inspect.stack()[0][3])
    if context.target:
        target = context.target.to_object
        grant_local_role_to_responsible(context, 'Reviewer', target)


@grok.subscribe(IValidation, IObjectAddedEvent)
@grok.subscribe(IOpinion, IObjectAddedEvent)
def set_contributor_on_document(context, event):
    """Set Contributor role on document to responsible after opinion and
    validation creation. (Contributor can create a new version)
    """
    log.info(inspect.stack()[0][3])
    document = context.getParentNode()
    grant_local_role_to_responsible(context, 'Contributor', document)


@grok.subscribe(IValidation, IObjectAddedEvent)
def set_editor_on_document(context, event):
    """Set Editor role on document to responsibile after validation
    creation."""
    log.info(inspect.stack()[0][3])
    document = context.getParentNode()
    grant_local_role_to_responsible(context, 'Editor', document)


@grok.subscribe(IDmsDocument, IObjectModifiedEvent)
def reindex_brain_metadata_on_basetask(doc, event):
    """Reindex brain metadatas when document is modified"""
    log.info(inspect.stack()[0][3])
    if isinstance(event, ContainerModifiedEvent):
        return

    catalog = api.portal.get_tool('portal_catalog')
    tasks = catalog.unrestrictedSearchResults({
        'object_provides': IBaseTask.__identifier__,
        'path': '/'.join(doc.getPhysicalPath())})
    for b in tasks:
        # reindex id index just to trigger the update of metadata on brain
        b._unrestrictedGetObject().reindexObject(idxs=['id'])


@grok.subscribe(IOpinion, IAfterTransitionEvent)
def set_reader_on_versions(context, event):
    """Set Reader role on Opinion enquirer on all versions created by
    the responsible when the Opinion is returned"""
    log.info(inspect.stack()[0][3])
    if event.new_state.id == 'done':
        responsible = context.responsible[0]
        enquirer = context.enquirer[0]
        container_path = '/'.join(context.getParentNode().getPhysicalPath())
        query = {'path': {'query': container_path},
                 'portal_type': 'dmsmainfile',
                 'Creator': responsible}
        catalog = api.portal.get_tool('portal_catalog')
        versions = catalog.searchResults(query)
        for brain in versions:
            version = brain.getObject()
            version.manage_addLocalRoles(enquirer, ['Reader'])
            version.reindexObject()
