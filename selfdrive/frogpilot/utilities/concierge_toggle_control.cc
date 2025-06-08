#include "selfdrive/frogpilot/utilities/concierge_toggle_control.h"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QProcess>
#include <QTimer>

#include "common/params.h"

ConciergeToggleControl::ConciergeToggleControl(QWidget *parent) 
  : ToggleControl("Concierge Web Server", "", "", Params().getBool("ConciergeEnabled"), parent),
    isHealthy(true), hasDependencies(true) {
  
  // Initialize diagnostics process
  diagnosticsProcess = new QProcess(this);
  connect(diagnosticsProcess, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
          this, &ConciergeToggleControl::onDiagnosticsFinished);
  
  // Initialize fix process  
  fixProcess = new QProcess(this);
  connect(fixProcess, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
          this, &ConciergeToggleControl::onFixProcessFinished);
  
  // Create fix button (will be added to description area)
  fixButton = new QPushButton("Fix");
  fixButton->setFixedSize(150, 80);
  fixButton->setStyleSheet(R"(
    QPushButton {
      font-size: 35px;
      padding: 10px 20px;
      background-color: #FF9800;
      color: white;
      border-radius: 5px;
    }
    QPushButton:pressed {
      background-color: #F57C00;
    }
    QPushButton:disabled {
      background-color: #999;
    }
  )");
  fixButton->hide();
  connect(fixButton, &QPushButton::clicked, this, &ConciergeToggleControl::onFixDependencies);
  
  // Add fix button to the main layout after description
  if (QVBoxLayout *mainLayout = qobject_cast<QVBoxLayout*>(layout())) {
    mainLayout->insertWidget(2, fixButton); // After hlayout and description
  }
  
  // Connect toggle changes
  connect(this, &ToggleControl::toggleFlipped, this, &ConciergeToggleControl::onToggleChanged);
  
  // Setup update timer
  updateTimer = new QTimer(this);
  updateTimer->setInterval(10000); // 10 seconds
  connect(updateTimer, &QTimer::timeout, this, &ConciergeToggleControl::updateStatus);
  updateTimer->start();
  
  // Initial update
  updateStatus();
}

void ConciergeToggleControl::updateStatus() {
  if (diagnosticsProcess->state() != QProcess::NotRunning) {
    return; // Already running
  }
  
  diagnosticsProcess->start("python3", QStringList() 
    << "/data/openpilot/selfdrive/frogpilot/utilities/concierge_diagnostics.py"
    << "--json");
}

void ConciergeToggleControl::onDiagnosticsFinished(int exitCode, QProcess::ExitStatus exitStatus) {
  if (exitStatus == QProcess::NormalExit && exitCode == 0) {
    QByteArray output = diagnosticsProcess->readAllStandardOutput();
    QJsonDocument doc = QJsonDocument::fromJson(output);
    
    if (!doc.isNull() && doc.isObject()) {
      updateDiagnostics(doc.object());
    }
  }
}

void ConciergeToggleControl::updateDiagnostics(const QJsonObject &diagnostics) {
  // Update health status
  QJsonObject health = diagnostics["health"].toObject();
  isHealthy = health["status"].toString() == "healthy";
  
  // Update dependencies status
  QJsonObject deps = diagnostics["dependencies"].toObject();
  QJsonObject pythonDeps = deps["python"].toObject();
  QJsonObject nodeDeps = deps["node"].toObject();
  
  missingPythonDeps.clear();
  missingNodeDeps.clear();
  
  for (const auto &dep : pythonDeps["missing"].toArray()) {
    missingPythonDeps << dep.toString();
  }
  
  for (const auto &dep : nodeDeps["missing"].toArray()) {
    missingNodeDeps << dep.toString();
  }
  
  hasDependencies = missingPythonDeps.isEmpty() && missingNodeDeps.isEmpty();
  
  // Update toggle state
  updateToggleState();
  
  // Format and set description
  QString desc = formatDiagnostics(diagnostics);
  setDescription(desc);
  
  // Show/hide fix button
  fixButton->setVisible(!hasDependencies);
}

QString ConciergeToggleControl::formatDiagnostics(const QJsonObject &diagnostics) {
  QString desc = "Enable the web-based management interface on port 5055\n\n";
  
  // Health status
  QJsonObject health = diagnostics["health"].toObject();
  QString healthIcon = health["status"].toString() == "healthy" ? "✅" : 
                      health["status"].toString() == "degraded" ? "⚠️" : "❌";
  desc += QString("Health: %1 %2 (%3/%4)\n")
    .arg(healthIcon)
    .arg(health["status"].toString().toUpper())
    .arg(health["score"].toInt())
    .arg(health["max_score"].toInt());
  
  // Process status
  QJsonObject process = diagnostics["process"].toObject();
  if (process["running"].toBool()) {
    desc += QString("Process: ✅ Running (PID %1)\n").arg(process["pid"].toInt());
    if (process.contains("memory_mb")) {
      desc += QString("Memory: %1 MB, CPU: %2%\n")
        .arg(process["memory_mb"].toDouble(), 0, 'f', 1)
        .arg(process["cpu_percent"].toDouble(), 0, 'f', 1);
    }
  } else {
    desc += "Process: ❌ Not running\n";
  }
  
  // HTTP status
  QJsonObject http = diagnostics["http"].toObject();
  if (http["http_responding"].toBool()) {
    desc += QString("HTTP: ✅ Responding (%1ms)\n")
      .arg(http["response_time_ms"].toDouble(), 0, 'f', 0);
  } else {
    desc += QString("HTTP: ❌ %1\n").arg(http["error"].toString());
  }
  
  // Port status
  QJsonObject port = diagnostics["port"].toObject();
  if (!port["port_open"].toBool() && port.contains("conflict")) {
    desc += QString("Port: ⚠️ In use by: %1\n").arg(port["conflict"].toString());
  }
  
  // Dependencies
  if (!hasDependencies) {
    desc += "\nMissing Dependencies:\n";
    
    if (!missingPythonDeps.isEmpty()) {
      desc += "Python: " + missingPythonDeps.join(", ") + "\n";
    }
    
    if (!missingNodeDeps.isEmpty()) {
      desc += "Node.js: " + missingNodeDeps.join(", ") + "\n";
      
      // Add TICI-specific message
      if (Params().getBool("IsOnroad") || QFile::exists("/TICI")) {
        desc += "\n⚠️ Tailwind CSS must be built offline\n";
        desc += "See: selfdrive/chauffeur/concierge/BUILD_TAILWIND.md\n";
      }
    }
  }
  
  // Recent errors
  QJsonObject logs = diagnostics["logs"].toObject();
  QJsonArray errors = logs["recent_errors"].toArray();
  if (!errors.isEmpty()) {
    desc += "\nRecent Errors:\n";
    for (const auto &error : errors) {
      QString errorStr = error.toString();
      // Wrap long lines
      if (errorStr.length() > 60) {
        errorStr = errorStr.left(57) + "...";
      }
      desc += "• " + errorStr + "\n";
    }
  }
  
  // System resources
  QJsonObject system = diagnostics["system"].toObject();
  if (system.contains("disk_free_gb") && system["disk_free_gb"].toDouble() < 5.0) {
    desc += QString("\n⚠️ Low disk space: %1 GB free\n")
      .arg(system["disk_free_gb"].toDouble(), 0, 'f', 1);
  }
  
  return desc.trimmed();
}

void ConciergeToggleControl::updateToggleState() {
  bool shouldEnable = hasDependencies;
  toggle.setEnabled(shouldEnable);
  
  if (!shouldEnable) {
    // Show a message when disabled
    setValue("Missing deps");
  } else if (!isHealthy) {
    setValue("Unhealthy");
  } else {
    setValue("");
  }
}

void ConciergeToggleControl::onToggleChanged(bool enabled) {
  params.putBool("ConciergeEnabled", enabled);
  
  if (enabled) {
    params.putBool("RestartConcierge", true);
    QProcess::execute("pkill", QStringList() << "-SIGHUP" << "manager");
  } else {
    params.putBool("StopConcierge", true);
    QProcess::execute("pkill", QStringList() << "-f" << "concierge.main");
  }
}

void ConciergeToggleControl::onFixDependencies() {
  if (fixProcess->state() != QProcess::NotRunning) {
    return; // Already running
  }
  
  fixButton->setEnabled(false);
  fixButton->setText("Installing...");
  
  // Update description to show progress
  QString currentDesc = getDescription();
  setDescription(currentDesc + "\n\n🔄 Installing dependencies...");
  
  // Build command
  QStringList args;
  args << "/data/openpilot/selfdrive/chauffeur/concierge/install_dependencies.py";
  
  if (!missingPythonDeps.isEmpty()) {
    args << "--python" << missingPythonDeps;
  }
  
  if (!missingNodeDeps.isEmpty()) {
    args << "--node" << missingNodeDeps;
  }
  
  fixProcess->start("python3", args);
  
  // Connect to readyRead to show real-time output
  connect(fixProcess, &QProcess::readyReadStandardOutput, this, [this]() {
    QByteArray output = fixProcess->readAllStandardOutput();
    QString lines = QString::fromUtf8(output);
    
    // Update description with latest output
    QString currentDesc = getDescription();
    QStringList descLines = currentDesc.split('\n');
    
    // Find where we started showing progress
    int progressStart = -1;
    for (int i = 0; i < descLines.size(); i++) {
      if (descLines[i].contains("Installing dependencies...")) {
        progressStart = i;
        break;
      }
    }
    
    if (progressStart >= 0) {
      // Keep everything up to progress start
      descLines = descLines.mid(0, progressStart + 1);
      
      // Add new output lines (wrapped)
      for (const QString &line : lines.split('\n')) {
        if (!line.trimmed().isEmpty()) {
          QString wrappedLine = line;
          if (wrappedLine.length() > 60) {
            wrappedLine = wrappedLine.left(57) + "...";
          }
          descLines << wrappedLine;
        }
      }
      
      setDescription(descLines.join('\n'));
    }
  });
}

void ConciergeToggleControl::onFixProcessFinished(int exitCode, QProcess::ExitStatus exitStatus) {
  fixButton->setEnabled(true);
  
  if (exitStatus == QProcess::NormalExit && exitCode == 0) {
    fixButton->setText("Fixed!");
    fixButton->setStyleSheet(fixButton->styleSheet().replace("#FF9800", "#4CAF50"));
    
    // Update status after a short delay
    QTimer::singleShot(1000, this, &ConciergeToggleControl::updateStatus);
    
    // Reset button after 3 seconds
    QTimer::singleShot(3000, this, [this]() {
      fixButton->setText("Fix");
      fixButton->setStyleSheet(fixButton->styleSheet().replace("#4CAF50", "#FF9800"));
    });
  } else {
    fixButton->setText("Fix Failed");
    fixButton->setStyleSheet(fixButton->styleSheet().replace("#FF9800", "#FF6B6B"));
    
    // Show error in description
    QString errorOutput = QString::fromUtf8(fixProcess->readAllStandardError());
    if (errorOutput.isEmpty()) {
      errorOutput = QString::fromUtf8(fixProcess->readAllStandardOutput());
    }
    
    QString currentDesc = getDescription();
    setDescription(currentDesc + "\n\n❌ Installation failed: " + errorOutput.left(200));
    
    // Reset button after 3 seconds
    QTimer::singleShot(3000, this, [this]() {
      fixButton->setText("Fix");
      fixButton->setStyleSheet(fixButton->styleSheet().replace("#FF6B6B", "#FF9800"));
    });
  }
}