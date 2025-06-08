#pragma once

#include <QTimer>
#include <QProcess>
#include <QPushButton>
#include <QJsonObject>
#include <QStringList>

#include "selfdrive/ui/qt/widgets/controls.h"
#include "common/params.h"

class ConciergeToggleControl : public ToggleControl {
  Q_OBJECT

public:
  explicit ConciergeToggleControl(QWidget *parent = nullptr);

private slots:
  void onToggleChanged(bool enabled);
  void updateToggleState();
  void updateStatus();
  void onDiagnosticsFinished(int exitCode, QProcess::ExitStatus exitStatus);
  void onFixDependencies();
  void onFixProcessFinished(int exitCode, QProcess::ExitStatus exitStatus);

private:
  void updateDiagnostics(const QJsonObject &diagnostics);
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