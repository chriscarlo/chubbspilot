# addressbook_fast.pyx
# distutils: language = c++
# distutils: include_dirs = /home/chris/openpilot/.venv/lib/python3.11/site-packages
# distutils: libraries = capnpc capnp capnp-rpc
# distutils: sources = offline.capnp.cpp
# cython: c_string_type = str
# cython: c_string_encoding = default
# cython: embedsignature = True


# TODO: add struct/enum/list types







import capnp
import offline_capnp

from capnp.includes.types cimport *
from capnp cimport helpers
from capnp.includes.capnp_cpp cimport DynamicValue, Schema, VOID, StringPtr, ArrayPtr, Data
from capnp.lib.capnp cimport _DynamicStructReader, _DynamicStructBuilder, _DynamicListBuilder, _DynamicEnum, _StructSchemaField, to_python_builder, to_python_reader, _to_dict, _setDynamicFieldStatic, _Schema, _InterfaceSchema

# Comment out problematic import - maybe not needed after changing except syntax?
# from capnp.helpers.non_circular cimport reraise_kj_exception

cdef DynamicValue.Reader _extract_dynamic_struct_builder(_DynamicStructBuilder value):
    return DynamicValue.Reader(value.thisptr.asReader())

cdef DynamicValue.Reader _extract_dynamic_struct_reader(_DynamicStructReader value):
    return DynamicValue.Reader(value.thisptr)

cdef DynamicValue.Reader _extract_dynamic_enum(_DynamicEnum value):
    return DynamicValue.Reader(value.thisptr)

cdef _from_list(_DynamicListBuilder msg, list d):
    cdef size_t count = 0
    for val in d:
        msg._set(count, val)
        count += 1


cdef extern from "offline.capnp.h":
    Schema getCoordinatesSchema"capnp::Schema::from<Coordinates>"()

    cdef cppclass Coordinates"Coordinates":
        cppclass Reader:
            DynamicValue.Reader getLatitude() except *
            DynamicValue.Reader getLongitude() except *
        cppclass Builder:
            DynamicValue.Builder getLatitude() except *
            void setLatitude(DynamicValue.Reader) except *
            DynamicValue.Builder getLongitude() except *
            void setLongitude(DynamicValue.Reader) except *
    Schema getWaySchema"capnp::Schema::from<Way>"()

    cdef cppclass Way"Way":
        cppclass Reader:
            StringPtr getName() except *

            StringPtr getRef() except *

            DynamicValue.Reader getMaxSpeed() except *
            DynamicValue.Reader getMinLat() except *
            DynamicValue.Reader getMinLon() except *
            DynamicValue.Reader getMaxLat() except *
            DynamicValue.Reader getMaxLon() except *
            DynamicValue.Reader getNodes() except *
            uint64_t getLanes() except *

            DynamicValue.Reader getAdvisorySpeed() except *
            StringPtr getHazard() except *

            cbool getOneWay() except *

        cppclass Builder:
            StringPtr getName() except *

            void setName(StringPtr) except *

            StringPtr getRef() except *

            void setRef(StringPtr) except *

            DynamicValue.Builder getMaxSpeed() except *
            void setMaxSpeed(DynamicValue.Reader) except *
            DynamicValue.Builder getMinLat() except *
            void setMinLat(DynamicValue.Reader) except *
            DynamicValue.Builder getMinLon() except *
            void setMinLon(DynamicValue.Reader) except *
            DynamicValue.Builder getMaxLat() except *
            void setMaxLat(DynamicValue.Reader) except *
            DynamicValue.Builder getMaxLon() except *
            void setMaxLon(DynamicValue.Reader) except *
            DynamicValue.Builder getNodes() except *
            void setNodes(DynamicValue.Reader) except *
            uint64_t getLanes() except *

            void setLanes(uint8_t) except *

            DynamicValue.Builder getAdvisorySpeed() except *
            void setAdvisorySpeed(DynamicValue.Reader) except *
            StringPtr getHazard() except *

            void setHazard(StringPtr) except *

            cbool getOneWay() except *

            void setOneWay(cbool) except *

    Schema getOfflineSchema"capnp::Schema::from<Offline>"()

    cdef cppclass Offline"Offline":
        cppclass Reader:
            DynamicValue.Reader getMinLat() except *
            DynamicValue.Reader getMinLon() except *
            DynamicValue.Reader getMaxLat() except *
            DynamicValue.Reader getMaxLon() except *
            DynamicValue.Reader getWays() except *
            DynamicValue.Reader getOverlap() except *
        cppclass Builder:
            DynamicValue.Builder getMinLat() except *
            void setMinLat(DynamicValue.Reader) except *
            DynamicValue.Builder getMinLon() except *
            void setMinLon(DynamicValue.Reader) except *
            DynamicValue.Builder getMaxLat() except *
            void setMaxLat(DynamicValue.Reader) except *
            DynamicValue.Builder getMaxLon() except *
            void setMaxLon(DynamicValue.Reader) except *
            DynamicValue.Builder getWays() except *
            void setWays(DynamicValue.Reader) except *
            DynamicValue.Builder getOverlap() except *
            void setOverlap(DynamicValue.Reader) except *

    cdef cppclass C_DynamicStruct_Reader" ::capnp::DynamicStruct::Reader":
        Coordinates.Reader asCoordinates"as<Coordinates>"()
        Way.Reader asWay"as<Way>"()
        Offline.Reader asOffline"as<Offline>"()

    cdef cppclass C_DynamicStruct_Builder" ::capnp::DynamicStruct::Builder":
        Coordinates.Builder asCoordinates"as<Coordinates>"()
        Way.Builder asWay"as<Way>"()
        Offline.Builder asOffline"as<Offline>"()

_Coordinates_Schema = _Schema()._init(getCoordinatesSchema()).as_struct()
offline_capnp.Coordinates.schema = _Coordinates_Schema

cdef class Coordinates_Reader(_DynamicStructReader):
    cdef Coordinates.Reader thisptr_child
    def __init__(self, _DynamicStructReader struct):
        self._init(struct.thisptr, struct._parent, struct.is_root, False)
        self.thisptr_child = (<C_DynamicStruct_Reader>struct.thisptr).asCoordinates()


    cpdef _get_latitude(self):
        cdef DynamicValue.Reader temp = self.thisptr_child.getLatitude()
        return to_python_reader(temp, self._parent)


    property latitude:
        def __get__(self):
            return self._get_latitude()

    cpdef _get_longitude(self):
        cdef DynamicValue.Reader temp = self.thisptr_child.getLongitude()
        return to_python_reader(temp, self._parent)


    property longitude:
        def __get__(self):
            return self._get_longitude()

    def to_dict(self, verbose=False, ordered=False):
        ret = {


        'latitude': _to_dict(self.latitude, verbose, ordered),


        'longitude': _to_dict(self.longitude, verbose, ordered),

        }



        return ret

cdef class Coordinates_Builder(_DynamicStructBuilder):
    cdef Coordinates.Builder thisptr_child
    def __init__(self, _DynamicStructBuilder struct):
        self._init(struct.thisptr, struct._parent, struct.is_root, False)
        self.thisptr_child = (<C_DynamicStruct_Builder>struct.thisptr).asCoordinates()

    cpdef _get_latitude(self):
        cdef DynamicValue.Builder temp = self.thisptr_child.getLatitude()
        return to_python_builder(temp, self._parent)

    cpdef _set_latitude(self, value):
        _setDynamicFieldStatic(self.thisptr, "latitude", value, self._parent)


    property latitude:
        def __get__(self):
            return self._get_latitude()
        def __set__(self, value):
            self._set_latitude(value)
    cpdef _get_longitude(self):
        cdef DynamicValue.Builder temp = self.thisptr_child.getLongitude()
        return to_python_builder(temp, self._parent)

    cpdef _set_longitude(self, value):
        _setDynamicFieldStatic(self.thisptr, "longitude", value, self._parent)


    property longitude:
        def __get__(self):
            return self._get_longitude()
        def __set__(self, value):
            self._set_longitude(value)

    def to_dict(self, verbose=False, ordered=False):
        ret = {


        'latitude': _to_dict(self.latitude, verbose, ordered),


        'longitude': _to_dict(self.longitude, verbose, ordered),

        }



        return ret

    def from_dict(self, dict d):
        cdef str key
        for key, val in d.iteritems():
            if False: pass

            elif key == "latitude":
                try:
                    self._set_latitude(val)
                except Exception as e:
                    if 'expected isSetInUnion(field)' in str(e):
                        self.init(key)
                        self._set_latitude(val)
                    else:
                        raise
            elif key == "longitude":
                try:
                    self._set_longitude(val)
                except Exception as e:
                    if 'expected isSetInUnion(field)' in str(e):
                        self.init(key)
                        self._set_longitude(val)
                    else:
                        raise
            else:
                raise ValueError('Key not found in struct: ' + key)


capnp.register_type(10532608661659469521, (Coordinates_Reader, Coordinates_Builder))


_Way_Schema = _Schema()._init(getWaySchema()).as_struct()
offline_capnp.Way.schema = _Way_Schema

cdef class Way_Reader(_DynamicStructReader):
    cdef Way.Reader thisptr_child
    def __init__(self, _DynamicStructReader struct):
        self._init(struct.thisptr, struct._parent, struct.is_root, False)
        self.thisptr_child = (<C_DynamicStruct_Reader>struct.thisptr).asWay()


    cpdef _get_name(self):
        temp = self.thisptr_child.getName()
        return (<char*>temp.begin())[:temp.size()]


    property name:
        def __get__(self):
            return self._get_name()

    cpdef _get_ref(self):
        temp = self.thisptr_child.getRef()
        return (<char*>temp.begin())[:temp.size()]


    property ref:
        def __get__(self):
            return self._get_ref()

    cpdef _get_maxSpeed(self):
        cdef DynamicValue.Reader temp = self.thisptr_child.getMaxSpeed()
        return to_python_reader(temp, self._parent)


    property maxSpeed:
        def __get__(self):
            return self._get_maxSpeed()

    cpdef _get_minLat(self):
        cdef DynamicValue.Reader temp = self.thisptr_child.getMinLat()
        return to_python_reader(temp, self._parent)


    property minLat:
        def __get__(self):
            return self._get_minLat()

    cpdef _get_minLon(self):
        cdef DynamicValue.Reader temp = self.thisptr_child.getMinLon()
        return to_python_reader(temp, self._parent)


    property minLon:
        def __get__(self):
            return self._get_minLon()

    cpdef _get_maxLat(self):
        cdef DynamicValue.Reader temp = self.thisptr_child.getMaxLat()
        return to_python_reader(temp, self._parent)


    property maxLat:
        def __get__(self):
            return self._get_maxLat()

    cpdef _get_maxLon(self):
        cdef DynamicValue.Reader temp = self.thisptr_child.getMaxLon()
        return to_python_reader(temp, self._parent)


    property maxLon:
        def __get__(self):
            return self._get_maxLon()

    cpdef _get_nodes(self):
        cdef DynamicValue.Reader temp = self.thisptr_child.getNodes()
        return to_python_reader(temp, self._parent)


    property nodes:
        def __get__(self):
            return self._get_nodes()

    cpdef _get_lanes(self):
        return self.thisptr_child.getLanes()


    property lanes:
        def __get__(self):
            return self._get_lanes()

    cpdef _get_advisorySpeed(self):
        cdef DynamicValue.Reader temp = self.thisptr_child.getAdvisorySpeed()
        return to_python_reader(temp, self._parent)


    property advisorySpeed:
        def __get__(self):
            return self._get_advisorySpeed()

    cpdef _get_hazard(self):
        temp = self.thisptr_child.getHazard()
        return (<char*>temp.begin())[:temp.size()]


    property hazard:
        def __get__(self):
            return self._get_hazard()

    cpdef _get_oneWay(self):
        return self.thisptr_child.getOneWay()


    property oneWay:
        def __get__(self):
            return self._get_oneWay()

    def to_dict(self, verbose=False, ordered=False):
        ret = {


        'name': _to_dict(self.name, verbose, ordered),


        'ref': _to_dict(self.ref, verbose, ordered),


        'maxSpeed': _to_dict(self.maxSpeed, verbose, ordered),


        'minLat': _to_dict(self.minLat, verbose, ordered),


        'minLon': _to_dict(self.minLon, verbose, ordered),


        'maxLat': _to_dict(self.maxLat, verbose, ordered),


        'maxLon': _to_dict(self.maxLon, verbose, ordered),


        'nodes': _to_dict(self.nodes, verbose, ordered),


        'lanes': _to_dict(self.lanes, verbose, ordered),


        'advisorySpeed': _to_dict(self.advisorySpeed, verbose, ordered),


        'hazard': _to_dict(self.hazard, verbose, ordered),


        'oneWay': _to_dict(self.oneWay, verbose, ordered),

        }



        return ret

cdef class Way_Builder(_DynamicStructBuilder):
    cdef Way.Builder thisptr_child
    def __init__(self, _DynamicStructBuilder struct):
        self._init(struct.thisptr, struct._parent, struct.is_root, False)
        self.thisptr_child = (<C_DynamicStruct_Builder>struct.thisptr).asWay()

    cpdef _get_name(self):
        temp = self.thisptr_child.getName()
        return (<char*>temp.begin())[:temp.size()]

    cpdef _set_name(self, value):
        cdef StringPtr temp_string
        if type(value) is bytes:
            temp_string = StringPtr(<char*>value, len(value))
        else:
            encoded_value = value.encode('utf-8')
            temp_string = StringPtr(<char*>encoded_value, len(encoded_value))
        self.thisptr_child.setName(temp_string)


    property name:
        def __get__(self):
            return self._get_name()
        def __set__(self, value):
            self._set_name(value)
    cpdef _get_ref(self):
        temp = self.thisptr_child.getRef()
        return (<char*>temp.begin())[:temp.size()]

    cpdef _set_ref(self, value):
        cdef StringPtr temp_string
        if type(value) is bytes:
            temp_string = StringPtr(<char*>value, len(value))
        else:
            encoded_value = value.encode('utf-8')
            temp_string = StringPtr(<char*>encoded_value, len(encoded_value))
        self.thisptr_child.setRef(temp_string)


    property ref:
        def __get__(self):
            return self._get_ref()
        def __set__(self, value):
            self._set_ref(value)
    cpdef _get_maxSpeed(self):
        cdef DynamicValue.Builder temp = self.thisptr_child.getMaxSpeed()
        return to_python_builder(temp, self._parent)

    cpdef _set_maxSpeed(self, value):
        _setDynamicFieldStatic(self.thisptr, "maxSpeed", value, self._parent)


    property maxSpeed:
        def __get__(self):
            return self._get_maxSpeed()
        def __set__(self, value):
            self._set_maxSpeed(value)
    cpdef _get_minLat(self):
        cdef DynamicValue.Builder temp = self.thisptr_child.getMinLat()
        return to_python_builder(temp, self._parent)

    cpdef _set_minLat(self, value):
        _setDynamicFieldStatic(self.thisptr, "minLat", value, self._parent)


    property minLat:
        def __get__(self):
            return self._get_minLat()
        def __set__(self, value):
            self._set_minLat(value)
    cpdef _get_minLon(self):
        cdef DynamicValue.Builder temp = self.thisptr_child.getMinLon()
        return to_python_builder(temp, self._parent)

    cpdef _set_minLon(self, value):
        _setDynamicFieldStatic(self.thisptr, "minLon", value, self._parent)


    property minLon:
        def __get__(self):
            return self._get_minLon()
        def __set__(self, value):
            self._set_minLon(value)
    cpdef _get_maxLat(self):
        cdef DynamicValue.Builder temp = self.thisptr_child.getMaxLat()
        return to_python_builder(temp, self._parent)

    cpdef _set_maxLat(self, value):
        _setDynamicFieldStatic(self.thisptr, "maxLat", value, self._parent)


    property maxLat:
        def __get__(self):
            return self._get_maxLat()
        def __set__(self, value):
            self._set_maxLat(value)
    cpdef _get_maxLon(self):
        cdef DynamicValue.Builder temp = self.thisptr_child.getMaxLon()
        return to_python_builder(temp, self._parent)

    cpdef _set_maxLon(self, value):
        _setDynamicFieldStatic(self.thisptr, "maxLon", value, self._parent)


    property maxLon:
        def __get__(self):
            return self._get_maxLon()
        def __set__(self, value):
            self._set_maxLon(value)
    cpdef _get_nodes(self):
        cdef DynamicValue.Builder temp = self.thisptr_child.getNodes()
        return to_python_builder(temp, self._parent)

    cpdef _set_nodes(self, list value):
        cdef uint i = 0
        self.init("nodes", len(value))
        cdef _DynamicListBuilder temp =  self._get_nodes()
        for elem in value:
            temp._get(i).from_dict(elem)
            i += 1


    property nodes:
        def __get__(self):
            return self._get_nodes()
        def __set__(self, value):
            self._set_nodes(value)
    cpdef _get_lanes(self):
        return self.thisptr_child.getLanes()

    cpdef _set_lanes(self, uint8_t value):
        self.thisptr_child.setLanes(value)


    property lanes:
        def __get__(self):
            return self._get_lanes()
        def __set__(self, value):
            self._set_lanes(value)
    cpdef _get_advisorySpeed(self):
        cdef DynamicValue.Builder temp = self.thisptr_child.getAdvisorySpeed()
        return to_python_builder(temp, self._parent)

    cpdef _set_advisorySpeed(self, value):
        _setDynamicFieldStatic(self.thisptr, "advisorySpeed", value, self._parent)


    property advisorySpeed:
        def __get__(self):
            return self._get_advisorySpeed()
        def __set__(self, value):
            self._set_advisorySpeed(value)
    cpdef _get_hazard(self):
        temp = self.thisptr_child.getHazard()
        return (<char*>temp.begin())[:temp.size()]

    cpdef _set_hazard(self, value):
        cdef StringPtr temp_string
        if type(value) is bytes:
            temp_string = StringPtr(<char*>value, len(value))
        else:
            encoded_value = value.encode('utf-8')
            temp_string = StringPtr(<char*>encoded_value, len(encoded_value))
        self.thisptr_child.setHazard(temp_string)


    property hazard:
        def __get__(self):
            return self._get_hazard()
        def __set__(self, value):
            self._set_hazard(value)
    cpdef _get_oneWay(self):
        return self.thisptr_child.getOneWay()

    cpdef _set_oneWay(self, cbool value):
        self.thisptr_child.setOneWay(value)


    property oneWay:
        def __get__(self):
            return self._get_oneWay()
        def __set__(self, value):
            self._set_oneWay(value)

    def to_dict(self, verbose=False, ordered=False):
        ret = {


        'name': _to_dict(self.name, verbose, ordered),


        'ref': _to_dict(self.ref, verbose, ordered),


        'maxSpeed': _to_dict(self.maxSpeed, verbose, ordered),


        'minLat': _to_dict(self.minLat, verbose, ordered),


        'minLon': _to_dict(self.minLon, verbose, ordered),


        'maxLat': _to_dict(self.maxLat, verbose, ordered),


        'maxLon': _to_dict(self.maxLon, verbose, ordered),


        'nodes': _to_dict(self.nodes, verbose, ordered),


        'lanes': _to_dict(self.lanes, verbose, ordered),


        'advisorySpeed': _to_dict(self.advisorySpeed, verbose, ordered),


        'hazard': _to_dict(self.hazard, verbose, ordered),


        'oneWay': _to_dict(self.oneWay, verbose, ordered),

        }



        return ret

    def from_dict(self, dict d):
        cdef str key
        for key, val in d.iteritems():
            if False: pass

            elif key == "name":
                try:
                    self._set_name(val)
                except Exception as e:
                    if 'expected isSetInUnion(field)' in str(e):
                        self.init(key)
                        self._set_name(val)
                    else:
                        raise
            elif key == "ref":
                try:
                    self._set_ref(val)
                except Exception as e:
                    if 'expected isSetInUnion(field)' in str(e):
                        self.init(key)
                        self._set_ref(val)
                    else:
                        raise
            elif key == "maxSpeed":
                try:
                    self._set_maxSpeed(val)
                except Exception as e:
                    if 'expected isSetInUnion(field)' in str(e):
                        self.init(key)
                        self._set_maxSpeed(val)
                    else:
                        raise
            elif key == "minLat":
                try:
                    self._set_minLat(val)
                except Exception as e:
                    if 'expected isSetInUnion(field)' in str(e):
                        self.init(key)
                        self._set_minLat(val)
                    else:
                        raise
            elif key == "minLon":
                try:
                    self._set_minLon(val)
                except Exception as e:
                    if 'expected isSetInUnion(field)' in str(e):
                        self.init(key)
                        self._set_minLon(val)
                    else:
                        raise
            elif key == "maxLat":
                try:
                    self._set_maxLat(val)
                except Exception as e:
                    if 'expected isSetInUnion(field)' in str(e):
                        self.init(key)
                        self._set_maxLat(val)
                    else:
                        raise
            elif key == "maxLon":
                try:
                    self._set_maxLon(val)
                except Exception as e:
                    if 'expected isSetInUnion(field)' in str(e):
                        self.init(key)
                        self._set_maxLon(val)
                    else:
                        raise
            elif key == "nodes":
                try:
                    self._set_nodes(val)
                except Exception as e:
                    if 'expected isSetInUnion(field)' in str(e):
                        self.init(key)
                        self._set_nodes(val)
                    else:
                        raise
            elif key == "lanes":
                try:
                    self._set_lanes(val)
                except Exception as e:
                    if 'expected isSetInUnion(field)' in str(e):
                        self.init(key)
                        self._set_lanes(val)
                    else:
                        raise
            elif key == "advisorySpeed":
                try:
                    self._set_advisorySpeed(val)
                except Exception as e:
                    if 'expected isSetInUnion(field)' in str(e):
                        self.init(key)
                        self._set_advisorySpeed(val)
                    else:
                        raise
            elif key == "hazard":
                try:
                    self._set_hazard(val)
                except Exception as e:
                    if 'expected isSetInUnion(field)' in str(e):
                        self.init(key)
                        self._set_hazard(val)
                    else:
                        raise
            elif key == "oneWay":
                try:
                    self._set_oneWay(val)
                except Exception as e:
                    if 'expected isSetInUnion(field)' in str(e):
                        self.init(key)
                        self._set_oneWay(val)
                    else:
                        raise
            else:
                raise ValueError('Key not found in struct: ' + key)


capnp.register_type(11869735526027662848, (Way_Reader, Way_Builder))


_Offline_Schema = _Schema()._init(getOfflineSchema()).as_struct()
offline_capnp.Offline.schema = _Offline_Schema

cdef class Offline_Reader(_DynamicStructReader):
    cdef Offline.Reader thisptr_child
    def __init__(self, _DynamicStructReader struct):
        self._init(struct.thisptr, struct._parent, struct.is_root, False)
        self.thisptr_child = (<C_DynamicStruct_Reader>struct.thisptr).asOffline()


    cpdef _get_minLat(self):
        cdef DynamicValue.Reader temp = self.thisptr_child.getMinLat()
        return to_python_reader(temp, self._parent)


    property minLat:
        def __get__(self):
            return self._get_minLat()

    cpdef _get_minLon(self):
        cdef DynamicValue.Reader temp = self.thisptr_child.getMinLon()
        return to_python_reader(temp, self._parent)


    property minLon:
        def __get__(self):
            return self._get_minLon()

    cpdef _get_maxLat(self):
        cdef DynamicValue.Reader temp = self.thisptr_child.getMaxLat()
        return to_python_reader(temp, self._parent)


    property maxLat:
        def __get__(self):
            return self._get_maxLat()

    cpdef _get_maxLon(self):
        cdef DynamicValue.Reader temp = self.thisptr_child.getMaxLon()
        return to_python_reader(temp, self._parent)


    property maxLon:
        def __get__(self):
            return self._get_maxLon()

    cpdef _get_ways(self):
        cdef DynamicValue.Reader temp = self.thisptr_child.getWays()
        return to_python_reader(temp, self._parent)


    property ways:
        def __get__(self):
            return self._get_ways()

    cpdef _get_overlap(self):
        cdef DynamicValue.Reader temp = self.thisptr_child.getOverlap()
        return to_python_reader(temp, self._parent)


    property overlap:
        def __get__(self):
            return self._get_overlap()

    def to_dict(self, verbose=False, ordered=False):
        ret = {


        'minLat': _to_dict(self.minLat, verbose, ordered),


        'minLon': _to_dict(self.minLon, verbose, ordered),


        'maxLat': _to_dict(self.maxLat, verbose, ordered),


        'maxLon': _to_dict(self.maxLon, verbose, ordered),


        'ways': _to_dict(self.ways, verbose, ordered),


        'overlap': _to_dict(self.overlap, verbose, ordered),

        }



        return ret

cdef class Offline_Builder(_DynamicStructBuilder):
    cdef Offline.Builder thisptr_child
    def __init__(self, _DynamicStructBuilder struct):
        self._init(struct.thisptr, struct._parent, struct.is_root, False)
        self.thisptr_child = (<C_DynamicStruct_Builder>struct.thisptr).asOffline()

    cpdef _get_minLat(self):
        cdef DynamicValue.Builder temp = self.thisptr_child.getMinLat()
        return to_python_builder(temp, self._parent)

    cpdef _set_minLat(self, value):
        _setDynamicFieldStatic(self.thisptr, "minLat", value, self._parent)


    property minLat:
        def __get__(self):
            return self._get_minLat()
        def __set__(self, value):
            self._set_minLat(value)
    cpdef _get_minLon(self):
        cdef DynamicValue.Builder temp = self.thisptr_child.getMinLon()
        return to_python_builder(temp, self._parent)

    cpdef _set_minLon(self, value):
        _setDynamicFieldStatic(self.thisptr, "minLon", value, self._parent)


    property minLon:
        def __get__(self):
            return self._get_minLon()
        def __set__(self, value):
            self._set_minLon(value)
    cpdef _get_maxLat(self):
        cdef DynamicValue.Builder temp = self.thisptr_child.getMaxLat()
        return to_python_builder(temp, self._parent)

    cpdef _set_maxLat(self, value):
        _setDynamicFieldStatic(self.thisptr, "maxLat", value, self._parent)


    property maxLat:
        def __get__(self):
            return self._get_maxLat()
        def __set__(self, value):
            self._set_maxLat(value)
    cpdef _get_maxLon(self):
        cdef DynamicValue.Builder temp = self.thisptr_child.getMaxLon()
        return to_python_builder(temp, self._parent)

    cpdef _set_maxLon(self, value):
        _setDynamicFieldStatic(self.thisptr, "maxLon", value, self._parent)


    property maxLon:
        def __get__(self):
            return self._get_maxLon()
        def __set__(self, value):
            self._set_maxLon(value)
    cpdef _get_ways(self):
        cdef DynamicValue.Builder temp = self.thisptr_child.getWays()
        return to_python_builder(temp, self._parent)

    cpdef _set_ways(self, list value):
        cdef uint i = 0
        self.init("ways", len(value))
        cdef _DynamicListBuilder temp =  self._get_ways()
        for elem in value:
            temp._get(i).from_dict(elem)
            i += 1


    property ways:
        def __get__(self):
            return self._get_ways()
        def __set__(self, value):
            self._set_ways(value)
    cpdef _get_overlap(self):
        cdef DynamicValue.Builder temp = self.thisptr_child.getOverlap()
        return to_python_builder(temp, self._parent)

    cpdef _set_overlap(self, value):
        _setDynamicFieldStatic(self.thisptr, "overlap", value, self._parent)


    property overlap:
        def __get__(self):
            return self._get_overlap()
        def __set__(self, value):
            self._set_overlap(value)

    def to_dict(self, verbose=False, ordered=False):
        ret = {


        'minLat': _to_dict(self.minLat, verbose, ordered),


        'minLon': _to_dict(self.minLon, verbose, ordered),


        'maxLat': _to_dict(self.maxLat, verbose, ordered),


        'maxLon': _to_dict(self.maxLon, verbose, ordered),


        'ways': _to_dict(self.ways, verbose, ordered),


        'overlap': _to_dict(self.overlap, verbose, ordered),

        }



        return ret

    def from_dict(self, dict d):
        cdef str key
        for key, val in d.iteritems():
            if False: pass

            elif key == "minLat":
                try:
                    self._set_minLat(val)
                except Exception as e:
                    if 'expected isSetInUnion(field)' in str(e):
                        self.init(key)
                        self._set_minLat(val)
                    else:
                        raise
            elif key == "minLon":
                try:
                    self._set_minLon(val)
                except Exception as e:
                    if 'expected isSetInUnion(field)' in str(e):
                        self.init(key)
                        self._set_minLon(val)
                    else:
                        raise
            elif key == "maxLat":
                try:
                    self._set_maxLat(val)
                except Exception as e:
                    if 'expected isSetInUnion(field)' in str(e):
                        self.init(key)
                        self._set_maxLat(val)
                    else:
                        raise
            elif key == "maxLon":
                try:
                    self._set_maxLon(val)
                except Exception as e:
                    if 'expected isSetInUnion(field)' in str(e):
                        self.init(key)
                        self._set_maxLon(val)
                    else:
                        raise
            elif key == "ways":
                try:
                    self._set_ways(val)
                except Exception as e:
                    if 'expected isSetInUnion(field)' in str(e):
                        self.init(key)
                        self._set_ways(val)
                    else:
                        raise
            elif key == "overlap":
                try:
                    self._set_overlap(val)
                except Exception as e:
                    if 'expected isSetInUnion(field)' in str(e):
                        self.init(key)
                        self._set_overlap(val)
                    else:
                        raise
            else:
                raise ValueError('Key not found in struct: ' + key)


capnp.register_type(14654698152418244832, (Offline_Reader, Offline_Builder))
