from zope.interface import implements
from zope import schema

from plone.autoform import directives as form
from plone.dexterity.content import Item
from plone.directives.form import default_value

from collective.task.interfaces import IBaseTask

from collective.z3cform.rolefield.field import LocalRolesToPrincipals
from collective.dms.basecontent.widget import AjaxChosenMultiFieldWidget

from collective.task import _

class IInformation(IBaseTask):
    """Schema for information"""
    form.mode(title='hidden')

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


class Information(Item):
    """Information content type"""
    implements(IInformation)

    meta_type = 'information'
    # disable local roles inheritance
    __ac_local_roles_block__ = True


@default_value(field=IInformation['title'])
def titleDefaultValue(data):
    return u"Pour information"
