/****************************************************************************
** Meta object code from reading C++ file 'concierge_toggle_control.h'
**
** Created by: The Qt Meta Object Compiler version 67 (Qt 5.12.8)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include "concierge_toggle_control.h"
#include <QtCore/qbytearray.h>
#include <QtCore/qmetatype.h>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'concierge_toggle_control.h' doesn't include <QObject>."
#elif Q_MOC_OUTPUT_REVISION != 67
#error "This file was generated using the moc from 5.12.8. It"
#error "cannot be used with the include files from this version of Qt."
#error "(The moc has changed too much.)"
#endif

QT_BEGIN_MOC_NAMESPACE
QT_WARNING_PUSH
QT_WARNING_DISABLE_DEPRECATED
struct qt_meta_stringdata_ConciergeToggleControl_t {
    QByteArrayData data[12];
    char stringdata0[181];
};
#define QT_MOC_LITERAL(idx, ofs, len) \
    Q_STATIC_BYTE_ARRAY_DATA_HEADER_INITIALIZER_WITH_OFFSET(len, \
    qptrdiff(offsetof(qt_meta_stringdata_ConciergeToggleControl_t, stringdata0) + ofs \
        - idx * sizeof(QByteArrayData)) \
    )
static const qt_meta_stringdata_ConciergeToggleControl_t qt_meta_stringdata_ConciergeToggleControl = {
    {
QT_MOC_LITERAL(0, 0, 22), // "ConciergeToggleControl"
QT_MOC_LITERAL(1, 23, 15), // "onToggleChanged"
QT_MOC_LITERAL(2, 39, 0), // ""
QT_MOC_LITERAL(3, 40, 7), // "enabled"
QT_MOC_LITERAL(4, 48, 17), // "updateToggleState"
QT_MOC_LITERAL(5, 66, 12), // "updateStatus"
QT_MOC_LITERAL(6, 79, 21), // "onDiagnosticsFinished"
QT_MOC_LITERAL(7, 101, 8), // "exitCode"
QT_MOC_LITERAL(8, 110, 20), // "QProcess::ExitStatus"
QT_MOC_LITERAL(9, 131, 10), // "exitStatus"
QT_MOC_LITERAL(10, 142, 17), // "onFixDependencies"
QT_MOC_LITERAL(11, 160, 20) // "onFixProcessFinished"

    },
    "ConciergeToggleControl\0onToggleChanged\0"
    "\0enabled\0updateToggleState\0updateStatus\0"
    "onDiagnosticsFinished\0exitCode\0"
    "QProcess::ExitStatus\0exitStatus\0"
    "onFixDependencies\0onFixProcessFinished"
};
#undef QT_MOC_LITERAL

static const uint qt_meta_data_ConciergeToggleControl[] = {

 // content:
       8,       // revision
       0,       // classname
       0,    0, // classinfo
       6,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       0,       // signalCount

 // slots: name, argc, parameters, tag, flags
       1,    1,   44,    2, 0x08 /* Private */,
       4,    0,   47,    2, 0x08 /* Private */,
       5,    0,   48,    2, 0x08 /* Private */,
       6,    2,   49,    2, 0x08 /* Private */,
      10,    0,   54,    2, 0x08 /* Private */,
      11,    2,   55,    2, 0x08 /* Private */,

 // slots: parameters
    QMetaType::Void, QMetaType::Bool,    3,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int, 0x80000000 | 8,    7,    9,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int, 0x80000000 | 8,    7,    9,

       0        // eod
};

void ConciergeToggleControl::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<ConciergeToggleControl *>(_o);
        Q_UNUSED(_t)
        switch (_id) {
        case 0: _t->onToggleChanged((*reinterpret_cast< bool(*)>(_a[1]))); break;
        case 1: _t->updateToggleState(); break;
        case 2: _t->updateStatus(); break;
        case 3: _t->onDiagnosticsFinished((*reinterpret_cast< int(*)>(_a[1])),(*reinterpret_cast< QProcess::ExitStatus(*)>(_a[2]))); break;
        case 4: _t->onFixDependencies(); break;
        case 5: _t->onFixProcessFinished((*reinterpret_cast< int(*)>(_a[1])),(*reinterpret_cast< QProcess::ExitStatus(*)>(_a[2]))); break;
        default: ;
        }
    }
}

QT_INIT_METAOBJECT const QMetaObject ConciergeToggleControl::staticMetaObject = { {
    &ToggleControl::staticMetaObject,
    qt_meta_stringdata_ConciergeToggleControl.data,
    qt_meta_data_ConciergeToggleControl,
    qt_static_metacall,
    nullptr,
    nullptr
} };


const QMetaObject *ConciergeToggleControl::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *ConciergeToggleControl::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_ConciergeToggleControl.stringdata0))
        return static_cast<void*>(this);
    return ToggleControl::qt_metacast(_clname);
}

int ConciergeToggleControl::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = ToggleControl::qt_metacall(_c, _id, _a);
    if (_id < 0)
        return _id;
    if (_c == QMetaObject::InvokeMetaMethod) {
        if (_id < 6)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 6;
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 6)
            *reinterpret_cast<int*>(_a[0]) = -1;
        _id -= 6;
    }
    return _id;
}
QT_WARNING_POP
QT_END_MOC_NAMESPACE
