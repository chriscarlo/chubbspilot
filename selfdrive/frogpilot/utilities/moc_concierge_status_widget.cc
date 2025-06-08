/****************************************************************************
** Meta object code from reading C++ file 'concierge_status_widget.h'
**
** Created by: The Qt Meta Object Compiler version 67 (Qt 5.15.13)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <memory>
#include "concierge_status_widget.h"
#include <QtCore/qbytearray.h>
#include <QtCore/qmetatype.h>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'concierge_status_widget.h' doesn't include <QObject>."
#elif Q_MOC_OUTPUT_REVISION != 67
#error "This file was generated using the moc from 5.15.13. It"
#error "cannot be used with the include files from this version of Qt."
#error "(The moc has changed too much.)"
#endif

QT_BEGIN_MOC_NAMESPACE
QT_WARNING_PUSH
QT_WARNING_DISABLE_DEPRECATED
struct qt_meta_stringdata_ConciergeStatusWidget_t {
    QByteArrayData data[16];
    char stringdata0[251];
};
#define QT_MOC_LITERAL(idx, ofs, len) \
    Q_STATIC_BYTE_ARRAY_DATA_HEADER_INITIALIZER_WITH_OFFSET(len, \
    qptrdiff(offsetof(qt_meta_stringdata_ConciergeStatusWidget_t, stringdata0) + ofs \
        - idx * sizeof(QByteArrayData)) \
    )
static const qt_meta_stringdata_ConciergeStatusWidget_t qt_meta_stringdata_ConciergeStatusWidget = {
    {
QT_MOC_LITERAL(0, 0, 21), // "ConciergeStatusWidget"
QT_MOC_LITERAL(1, 22, 19), // "healthStatusChanged"
QT_MOC_LITERAL(2, 42, 0), // ""
QT_MOC_LITERAL(3, 43, 9), // "isHealthy"
QT_MOC_LITERAL(4, 53, 25), // "dependenciesStatusChanged"
QT_MOC_LITERAL(5, 79, 10), // "hasMissing"
QT_MOC_LITERAL(6, 90, 13), // "missingPython"
QT_MOC_LITERAL(7, 104, 11), // "missingNode"
QT_MOC_LITERAL(8, 116, 12), // "updateStatus"
QT_MOC_LITERAL(9, 129, 21), // "onDiagnosticsFinished"
QT_MOC_LITERAL(10, 151, 8), // "exitCode"
QT_MOC_LITERAL(11, 160, 20), // "QProcess::ExitStatus"
QT_MOC_LITERAL(12, 181, 10), // "exitStatus"
QT_MOC_LITERAL(13, 192, 17), // "onFixDependencies"
QT_MOC_LITERAL(14, 210, 19), // "onRelaunchConcierge"
QT_MOC_LITERAL(15, 230, 20) // "onFixProcessFinished"

    },
    "ConciergeStatusWidget\0healthStatusChanged\0"
    "\0isHealthy\0dependenciesStatusChanged\0"
    "hasMissing\0missingPython\0missingNode\0"
    "updateStatus\0onDiagnosticsFinished\0"
    "exitCode\0QProcess::ExitStatus\0exitStatus\0"
    "onFixDependencies\0onRelaunchConcierge\0"
    "onFixProcessFinished"
};
#undef QT_MOC_LITERAL

static const uint qt_meta_data_ConciergeStatusWidget[] = {

 // content:
       8,       // revision
       0,       // classname
       0,    0, // classinfo
       7,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       2,       // signalCount

 // signals: name, argc, parameters, tag, flags
       1,    1,   49,    2, 0x06 /* Public */,
       4,    3,   52,    2, 0x06 /* Public */,

 // slots: name, argc, parameters, tag, flags
       8,    0,   59,    2, 0x08 /* Private */,
       9,    2,   60,    2, 0x08 /* Private */,
      13,    0,   65,    2, 0x08 /* Private */,
      14,    0,   66,    2, 0x08 /* Private */,
      15,    2,   67,    2, 0x08 /* Private */,

 // signals: parameters
    QMetaType::Void, QMetaType::Bool,    3,
    QMetaType::Void, QMetaType::Bool, QMetaType::QStringList, QMetaType::QStringList,    5,    6,    7,

 // slots: parameters
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int, 0x80000000 | 11,   10,   12,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int, 0x80000000 | 11,   10,   12,

       0        // eod
};

void ConciergeStatusWidget::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<ConciergeStatusWidget *>(_o);
        (void)_t;
        switch (_id) {
        case 0: _t->healthStatusChanged((*reinterpret_cast< bool(*)>(_a[1]))); break;
        case 1: _t->dependenciesStatusChanged((*reinterpret_cast< bool(*)>(_a[1])),(*reinterpret_cast< const QStringList(*)>(_a[2])),(*reinterpret_cast< const QStringList(*)>(_a[3]))); break;
        case 2: _t->updateStatus(); break;
        case 3: _t->onDiagnosticsFinished((*reinterpret_cast< int(*)>(_a[1])),(*reinterpret_cast< QProcess::ExitStatus(*)>(_a[2]))); break;
        case 4: _t->onFixDependencies(); break;
        case 5: _t->onRelaunchConcierge(); break;
        case 6: _t->onFixProcessFinished((*reinterpret_cast< int(*)>(_a[1])),(*reinterpret_cast< QProcess::ExitStatus(*)>(_a[2]))); break;
        default: ;
        }
    } else if (_c == QMetaObject::IndexOfMethod) {
        int *result = reinterpret_cast<int *>(_a[0]);
        {
            using _t = void (ConciergeStatusWidget::*)(bool );
            if (*reinterpret_cast<_t *>(_a[1]) == static_cast<_t>(&ConciergeStatusWidget::healthStatusChanged)) {
                *result = 0;
                return;
            }
        }
        {
            using _t = void (ConciergeStatusWidget::*)(bool , const QStringList & , const QStringList & );
            if (*reinterpret_cast<_t *>(_a[1]) == static_cast<_t>(&ConciergeStatusWidget::dependenciesStatusChanged)) {
                *result = 1;
                return;
            }
        }
    }
}

QT_INIT_METAOBJECT const QMetaObject ConciergeStatusWidget::staticMetaObject = { {
    QMetaObject::SuperData::link<QFrame::staticMetaObject>(),
    qt_meta_stringdata_ConciergeStatusWidget.data,
    qt_meta_data_ConciergeStatusWidget,
    qt_static_metacall,
    nullptr,
    nullptr
} };


const QMetaObject *ConciergeStatusWidget::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *ConciergeStatusWidget::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_ConciergeStatusWidget.stringdata0))
        return static_cast<void*>(this);
    return QFrame::qt_metacast(_clname);
}

int ConciergeStatusWidget::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = QFrame::qt_metacall(_c, _id, _a);
    if (_id < 0)
        return _id;
    if (_c == QMetaObject::InvokeMetaMethod) {
        if (_id < 7)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 7;
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 7)
            *reinterpret_cast<int*>(_a[0]) = -1;
        _id -= 7;
    }
    return _id;
}

// SIGNAL 0
void ConciergeStatusWidget::healthStatusChanged(bool _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 0, _a);
}

// SIGNAL 1
void ConciergeStatusWidget::dependenciesStatusChanged(bool _t1, const QStringList & _t2, const QStringList & _t3)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))), const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t2))), const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t3))) };
    QMetaObject::activate(this, &staticMetaObject, 1, _a);
}
struct qt_meta_stringdata_ConciergeToggleControl_t {
    QByteArrayData data[5];
    char stringdata0[66];
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
QT_MOC_LITERAL(4, 48, 17) // "updateToggleState"

    },
    "ConciergeToggleControl\0onToggleChanged\0"
    "\0enabled\0updateToggleState"
};
#undef QT_MOC_LITERAL

static const uint qt_meta_data_ConciergeToggleControl[] = {

 // content:
       8,       // revision
       0,       // classname
       0,    0, // classinfo
       2,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       0,       // signalCount

 // slots: name, argc, parameters, tag, flags
       1,    1,   24,    2, 0x08 /* Private */,
       4,    0,   27,    2, 0x08 /* Private */,

 // slots: parameters
    QMetaType::Void, QMetaType::Bool,    3,
    QMetaType::Void,

       0        // eod
};

void ConciergeToggleControl::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<ConciergeToggleControl *>(_o);
        (void)_t;
        switch (_id) {
        case 0: _t->onToggleChanged((*reinterpret_cast< bool(*)>(_a[1]))); break;
        case 1: _t->updateToggleState(); break;
        default: ;
        }
    }
}

QT_INIT_METAOBJECT const QMetaObject ConciergeToggleControl::staticMetaObject = { {
    QMetaObject::SuperData::link<ToggleControl::staticMetaObject>(),
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
        if (_id < 2)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 2;
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 2)
            *reinterpret_cast<int*>(_a[0]) = -1;
        _id -= 2;
    }
    return _id;
}
struct qt_meta_stringdata_ConciergeManagementControl_t {
    QByteArrayData data[1];
    char stringdata0[27];
};
#define QT_MOC_LITERAL(idx, ofs, len) \
    Q_STATIC_BYTE_ARRAY_DATA_HEADER_INITIALIZER_WITH_OFFSET(len, \
    qptrdiff(offsetof(qt_meta_stringdata_ConciergeManagementControl_t, stringdata0) + ofs \
        - idx * sizeof(QByteArrayData)) \
    )
static const qt_meta_stringdata_ConciergeManagementControl_t qt_meta_stringdata_ConciergeManagementControl = {
    {
QT_MOC_LITERAL(0, 0, 26) // "ConciergeManagementControl"

    },
    "ConciergeManagementControl"
};
#undef QT_MOC_LITERAL

static const uint qt_meta_data_ConciergeManagementControl[] = {

 // content:
       8,       // revision
       0,       // classname
       0,    0, // classinfo
       0,    0, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       0,       // signalCount

       0        // eod
};

void ConciergeManagementControl::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    (void)_o;
    (void)_id;
    (void)_c;
    (void)_a;
}

QT_INIT_METAOBJECT const QMetaObject ConciergeManagementControl::staticMetaObject = { {
    QMetaObject::SuperData::link<QFrame::staticMetaObject>(),
    qt_meta_stringdata_ConciergeManagementControl.data,
    qt_meta_data_ConciergeManagementControl,
    qt_static_metacall,
    nullptr,
    nullptr
} };


const QMetaObject *ConciergeManagementControl::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *ConciergeManagementControl::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_ConciergeManagementControl.stringdata0))
        return static_cast<void*>(this);
    return QFrame::qt_metacast(_clname);
}

int ConciergeManagementControl::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = QFrame::qt_metacall(_c, _id, _a);
    return _id;
}
QT_WARNING_POP
QT_END_MOC_NAMESPACE
