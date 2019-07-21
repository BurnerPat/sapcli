"""ATC ADT wrappers"""

import xml.sax
from xml.sax.handler import ContentHandler

from typing import NamedTuple

from sap import get_logger
from sap.adt.objects import OrderedClassMembers, ADTObjectType, XMLNamespace, xmlns_adtcore_ancestor
from sap.adt.annotations import xml_element, XmlNodeProperty, xml_text_node_property, XmlContainer, \
    XmlNodeAttributeProperty
from sap.adt.marshalling import Marshal


CUSTOMIZING_MIME_TYPE_V1 = 'application/vnd.sap.atc.customizing-v1+xml'

XMLNS_ATC = XMLNamespace('atc', 'http://www.sap.com/adt/atc')
XMLNS_ATCINFO = XMLNamespace('atcinfo', 'http://www.sap.com/adt/atc/info')
XMLNS_ATCWORKLIST = XMLNamespace('atcworklist', 'http://www.sap.com/adt/atc/worklist')
XMLNS_ATCOBJECT = xmlns_adtcore_ancestor('atcobject', 'http://www.sap.com/adt/atc/object')
XMLNS_ATCFINDING = XMLNamespace('atcfinding', 'http://www.sap.com/adt/atc/finding')


def mod_log():
    """Returns logger for this module"""

    return get_logger()


class ATCCustomizingXMLHandler(ContentHandler):
    """ATC Customizing XML parser"""

    def __init__(self, customizing):
        """:param customizing: A object with the target attributes"""
        super(ATCCustomizingXMLHandler, self).__init__()

        self.customizing = customizing

    def startElement(self, name, attrs):
        if name == 'property' and attrs.get('name', None) == 'systemCheckVariant':
            self.customizing.system_check_variant = attrs.get('value', None)


# pylint: disable=too-few-public-methods
class Customizing:
    """ATC Customizing"""

    def __init__(self, system_check_variant=None):
        self.system_check_variant = system_check_variant


def fetch_customizing(connection):
    """Fetch ATC customizing for the connected system"""

    resp = connection.execute(
        'GET',
        'atc/customizing',
        accept=['application/xml', CUSTOMIZING_MIME_TYPE_V1]
    )

    mod_log().debug('ATC Customizing response:\n%s', resp.text)

    cust = Customizing()
    xml.sax.parseString(resp.text, ATCCustomizingXMLHandler(cust))

    return cust


class RunRequest(metaclass=OrderedClassMembers):
    """Worklist run Request"""

    objtype = ADTObjectType(None, None, XMLNS_ATC, 'application/xml', None, 'run')

    max_verdicts = XmlNodeAttributeProperty('maximumVerdicts')

    def __init__(self, obj_sets, max_verdicts):
        """:param obj_sets: An instance of :class:`ADTObjectSets`
           :param max_verdicts: A number
        """
        self._sets = obj_sets
        self.max_verdicts = max_verdicts

    @xml_element('objectSets')
    def sets(self):
        """Set of objects which we want to check"""

        return self._sets


class ATCInfo(metaclass=OrderedClassMembers):
    """atcinfo:info XML Node"""

    objtype = ADTObjectType(None, None, XMLNS_ATCINFO, 'application/xml', None, 'info')

    typ = xml_text_node_property('atcinfo:type')
    description = xml_text_node_property('atcinfo:description')

    def __str__(self):
        return self.description


# pylint: disable=invalid-name
ATCInfoList = XmlContainer.define(ATCInfo.objtype.xmlelement, ATCInfo)


class RunResponse(metaclass=OrderedClassMembers):
    """Worklist run Response"""

    objtype = ADTObjectType(None, None, XMLNS_ATCWORKLIST, 'application/xml', None, 'worklistRun')

    worklist_id = xml_text_node_property('atcworklist:worklistId')
    timestamp = xml_text_node_property('atcworklist:worklistTimestamp')
    infos = XmlNodeProperty('atcworklist:infos', factory=ATCInfoList)


class WorkListObjectSet(metaclass=OrderedClassMembers):
    """atcworklist:objectSet XML Node"""

    name = XmlNodeAttributeProperty('atcworklist:name')
    title = XmlNodeAttributeProperty('atcworklist:title')
    kind = XmlNodeAttributeProperty('atcworklist:kind')


# pylint: disable=invalid-name
WorkListObjectSetList = XmlContainer.define('atcworklist:objectSet', WorkListObjectSet)


class ATCFinding(metaclass=OrderedClassMembers):
    """atcfinding:finding XML Node"""

    uri = XmlNodeAttributeProperty('adtcore:uri')
    location = XmlNodeAttributeProperty('atcfinding:location')
    priority = XmlNodeAttributeProperty('atcfinding:priority')
    check_id = XmlNodeAttributeProperty('atcfinding:checkId')
    check_title = XmlNodeAttributeProperty('atcfinding:checkTitle')
    message_id = XmlNodeAttributeProperty('atcfinding:messageId')
    message_title = XmlNodeAttributeProperty('atcfinding:messageTitle')
    exemption_approval = XmlNodeAttributeProperty('atcfinding:exemptionApproval')
    exemption_kind = XmlNodeAttributeProperty('atcfinding:exemptionKind')


# pylint: disable=invalid-name
ATCFindingList = XmlContainer.define('atcfinding:finding', ATCFinding)


class ATCObject(metaclass=OrderedClassMembers):
    """atcobject:object XML Node"""

    objtype = ADTObjectType(None, None, XMLNS_ATCOBJECT, 'application/xml', None, 'object')

    uri = XmlNodeAttributeProperty('adtcore:uri')
    typ = XmlNodeAttributeProperty('adtcore:type')
    name = XmlNodeAttributeProperty('adtcore:name')
    package_name = XmlNodeAttributeProperty('adtcore:packageName')
    author = XmlNodeAttributeProperty('atcobject:author')
    object_type_id = XmlNodeAttributeProperty('atcobject:objectTypeId')
    findings = XmlNodeProperty('atcobject:findings', factory=ATCFindingList)


# pylint: disable=invalid-name
ATCObjectList = XmlContainer.define('atcobject:object', ATCObject)


class WorkList(metaclass=OrderedClassMembers):
    """atcworklist:worklist XML Node"""

    objtype = ADTObjectType(None, None, XMLNS_ATCWORKLIST, 'application/xml', None, 'worklist')

    worklist_id = XmlNodeAttributeProperty('atcworklist:id')
    timestamp = XmlNodeAttributeProperty('atcworklist:timestamp')
    used_objectset = XmlNodeAttributeProperty('atcworklist:usedObjectSet')
    object_set_is_complete = XmlNodeAttributeProperty('atcworklist:objectSetIsComplete')
    object_sets = XmlNodeProperty('atcworklist:objectSets', factory=WorkListObjectSetList)
    objects = XmlNodeProperty('atcworklist:objects', factory=ATCObjectList)


class WorkListRunResult(NamedTuple):
    """Work List Run results"""

    run_response: RunResponse
    worklist: WorkList


class ChecksRunner:
    """"ATC Checks runner"""

    def __init__(self, connection, variant):
        """:param connection: ADT Connection
           :param variant: A string holding the executed variant name
        """
        self._connection = connection
        self._variant = variant
        self._worklist_id = None

    def _get_id(self):
        """Fetches this list's ID"""

        if self._worklist_id is None:
            resp = self._connection.execute('POST', 'atc/worklists',
                                            params={'checkVariant': self._variant},
                                            accept='text/plain')
            self._worklist_id = resp.text

        return self._worklist_id

    def run_for(self, obj_sets, max_verdicts=100):
        """Executes checks for the given object sets"""

        run_request = RunRequest(obj_sets, max_verdicts)
        request = Marshal().serialize(run_request)

        worklist_id = self._get_id()
        resp = self._connection.execute('POST', 'atc/runs', params={'worklistId': worklist_id},
                                        accept='application/xml', content_type='application/xml',
                                        body=request)

        run_response = RunResponse()
        Marshal.deserialize(resp.text, run_response)

        resp = self._connection.execute('GET', f'atc/worklists/{worklist_id}',
                                        params={'includeExemptedFindings': 'false'},
                                        accept='application/atc.worklist.v1+xml')

        worklist = WorkList()
        Marshal.deserialize(resp.text, worklist)

        return WorkListRunResult(run_response, worklist)
