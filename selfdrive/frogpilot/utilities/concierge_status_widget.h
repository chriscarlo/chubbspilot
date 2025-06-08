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

#include "selfdrive/ui/qt/widgets/controls.h"
#include "selfdrive/frogpilot/ui/qt/widgets/frogpilot_controls.h"

class ConciergeStatusWidget : public QFrame {
  Q_OBJECT

public:
  explicit ConciergeStatusWidget(QWidget *parent = nullptr);

private slots:
  void updateStatus();
  void onDiagnosticsFinished(int exitCode, QProcess::ExitStatus exitStatus);

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
  
  QTimer *updateTimer;
  QProcess *diagnosticsProcess;
  
  bool isUpdating;
};

class ConciergeToggleControl : public ToggleControl {
  Q_OBJECT

public:
  ConciergeToggleControl();

private slots:
  void onToggleChanged(bool enabled);

private:
  Params params;
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