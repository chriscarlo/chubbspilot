#pragma once

#include <QTimer>
#include <QLabel>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGridLayout>
#include <QFrame>
#include <QProcess>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QStringList>
#include <QPushButton>

#include "selfdrive/ui/qt/widgets/controls.h"
#include "selfdrive/frogpilot/ui/qt/widgets/frogpilot_controls.h"

class ConciergeStatusWidget : public QFrame {
  Q_OBJECT

public:
  explicit ConciergeStatusWidget(QWidget *parent = nullptr);

signals:
  void healthStatusChanged(bool isHealthy);
  void dependenciesStatusChanged(bool hasMissing, const QStringList &missingPython, const QStringList &missingNode);

private slots:
  void updateStatus();
  void onDiagnosticsFinished(int exitCode, QProcess::ExitStatus exitStatus);
  void onFixDependencies();
  void onRelaunchConcierge();
  void onFixProcessFinished(int exitCode, QProcess::ExitStatus exitStatus);

private:
  void setupUI();
  void updateDisplay(const QJsonObject &diagnostics);
  QString formatHealth(const QJsonObject &health);
  QString formatProcess(const QJsonObject &process);
  QString formatHttp(const QJsonObject &http);
  QString formatSystem(const QJsonObject &system);
  QString formatErrors(const QJsonObject &logs);

  QVBoxLayout *mainLayout;
  QLabel *titleLabel;
  QLabel *docLabel;
  QLabel *healthLabel;
  QLabel *processLabel;
  QLabel *httpLabel;
  QLabel *portLabel;
  QLabel *depsLabel;
  QLabel *errorsLabel;
  QLabel *lastUpdatedLabel;
  
  QPushButton *fixButton;
  
  QHBoxLayout *actionsLayout;
  QPushButton *relaunchButton;
  
  QTimer *updateTimer;
  QProcess *diagnosticsProcess;
  QProcess *fixProcess;
  
  bool isUpdating;
  bool isHealthy;
  QStringList missingPythonDeps;
  QStringList missingNodeDeps;
};

class ConciergeToggleControl : public ToggleControl {
  Q_OBJECT

public:
  ConciergeToggleControl();
  void setHealthy(bool healthy);
  void setDependenciesOk(bool ok);
  void updateDiagnostics(const QJsonObject &diagnostics);

private slots:
  void onToggleChanged(bool enabled);
  void updateToggleState();
  void updateStatus();
  void onDiagnosticsFinished(int exitCode, QProcess::ExitStatus exitStatus);
  void onFixDependencies();
  void onFixProcessFinished(int exitCode, QProcess::ExitStatus exitStatus);

private:
  QString formatDiagnostics(const QJsonObject &diagnostics);
  
  Params params;
  bool isHealthy;
  bool hasDependencies;
  QTimer *updateTimer;
  QProcess *diagnosticsProcess;
  QProcess *fixProcess;
  QPushButton *fixButton;
  QStringList missingPythonDeps;
  QStringList missingNodeDeps;
};

class ConciergeManagementControl : public QFrame {
  Q_OBJECT

public:
  explicit ConciergeManagementControl(QWidget *parent = nullptr);

private:
  ConciergeToggleControl *toggleControl;
  ConciergeStatusWidget *statusWidget;
  QVBoxLayout *mainLayout;
};