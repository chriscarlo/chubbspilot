#include "selfdrive/frogpilot/utilities/concierge_status_widget.h"

#include <QDateTime>
#include <QDebug>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonValue>

ConciergeStatusWidget::ConciergeStatusWidget(QWidget *parent) : QFrame(parent), isUpdating(false) {
  setupUI();
  
  // Set up update timer (every 10 seconds)
  updateTimer = new QTimer(this);
  connect(updateTimer, &QTimer::timeout, this, &ConciergeStatusWidget::updateStatus);
  updateTimer->start(10000);
  
  // Set up diagnostics process
  diagnosticsProcess = new QProcess(this);
  connect(diagnosticsProcess, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
          this, &ConciergeStatusWidget::onDiagnosticsFinished);
  
  // Initial update
  updateStatus();
}

void ConciergeStatusWidget::setupUI() {
  mainLayout = new QVBoxLayout(this);
  mainLayout->setSpacing(15);
  mainLayout->setMargin(20);
  
  // Title with documentation hint
  titleLabel = new QLabel("Concierge Web Server Status", this);
  titleLabel->setStyleSheet("font-size: 45px; font-weight: 500; color: #E4E4E4; margin-bottom: 20px;");
  mainLayout->addWidget(titleLabel);
  
  // Documentation hint
  docLabel = new QLabel("See /data/openpilot/selfdrive/chauffeur/concierge/README.md for details", this);
  docLabel->setStyleSheet("font-size: 35px; color: #888888; margin-bottom: 30px;");
  mainLayout->addWidget(docLabel);
  
  // Health status with larger font
  healthLabel = new QLabel("Health: Checking...", this);
  healthLabel->setStyleSheet("font-size: 40px; font-weight: 600; margin-bottom: 20px;");
  mainLayout->addWidget(healthLabel);
  
  // Process status - clearer formatting
  processLabel = new QLabel("Process: Checking...", this);
  processLabel->setStyleSheet("font-size: 35px; color: #E4E4E4; margin-bottom: 15px; padding-left: 40px;");
  mainLayout->addWidget(processLabel);
  
  // HTTP status - more informative
  httpLabel = new QLabel("HTTP: Checking...", this);
  httpLabel->setStyleSheet("font-size: 35px; color: #E4E4E4; margin-bottom: 15px; padding-left: 40px;");
  mainLayout->addWidget(httpLabel);
  
  // Port status - new field for clarity
  portLabel = new QLabel("Port: Checking...", this);
  portLabel->setStyleSheet("font-size: 35px; color: #E4E4E4; margin-bottom: 15px; padding-left: 40px;");
  mainLayout->addWidget(portLabel);
  
  // Dependencies status
  depsLabel = new QLabel("Dependencies: Checking...", this);
  depsLabel->setStyleSheet("font-size: 35px; color: #E4E4E4; margin-bottom: 15px; padding-left: 40px;");
  mainLayout->addWidget(depsLabel);
  
  // Recent errors - more prominent
  errorsLabel = new QLabel("", this);
  errorsLabel->setStyleSheet("font-size: 35px; color: #FF6B6B; margin-top: 20px; margin-bottom: 20px; padding-left: 40px;");
  errorsLabel->setWordWrap(true);
  mainLayout->addWidget(errorsLabel);
  
  // Last updated
  lastUpdatedLabel = new QLabel("Last updated: Never", this);
  lastUpdatedLabel->setStyleSheet("font-size: 30px; color: #888888; margin-top: 20px;");
  mainLayout->addWidget(lastUpdatedLabel);
  
  // Remove fixed height and frame styling - let it flow naturally
  setStyleSheet("QFrame { background-color: transparent; }");
}

void ConciergeStatusWidget::updateStatus() {
  if (isUpdating || diagnosticsProcess->state() != QProcess::NotRunning) {
    return;
  }
  
  isUpdating = true;
  
  // Run diagnostics script
  QString scriptPath = "/data/openpilot/selfdrive/frogpilot/utilities/concierge_diagnostics.py";
  diagnosticsProcess->start("python3", QStringList() << scriptPath << "--json");
}

void ConciergeStatusWidget::onDiagnosticsFinished(int exitCode, QProcess::ExitStatus exitStatus) {
  isUpdating = false;
  
  if (exitStatus == QProcess::NormalExit && exitCode == 0) {
    QByteArray output = diagnosticsProcess->readAllStandardOutput();
    QJsonDocument doc = QJsonDocument::fromJson(output);
    
    if (!doc.isNull() && doc.isObject()) {
      updateDisplay(doc.object());
    } else {
      healthLabel->setText("Health: ❌ Data Parse Error");
      healthLabel->setStyleSheet("font-size: 16px; font-weight: bold; color: #FF6B6B; margin-bottom: 5px;");
    }
  } else {
    healthLabel->setText("Health: ❌ Script Error");
    healthLabel->setStyleSheet("font-size: 16px; font-weight: bold; color: #FF6B6B; margin-bottom: 5px;");
  }
  
  // Update timestamp
  QString timestamp = QDateTime::currentDateTime().toString("hh:mm:ss");
  lastUpdatedLabel->setText(QString("Last updated: %1").arg(timestamp));
}

void ConciergeStatusWidget::updateDisplay(const QJsonObject &diagnostics) {
  // Health status
  if (diagnostics.contains("health")) {
    QString healthText = formatHealth(diagnostics["health"].toObject());
    healthLabel->setText(healthText);
  }
  
  // Process status
  if (diagnostics.contains("process")) {
    QString processText = formatProcess(diagnostics["process"].toObject());
    processLabel->setText(processText);
  }
  
  // HTTP status
  if (diagnostics.contains("http")) {
    QString httpText = formatHttp(diagnostics["http"].toObject());
    httpLabel->setText(httpText);
  }
  
  // Port status
  if (diagnostics.contains("port")) {
    QJsonObject port = diagnostics["port"].toObject();
    bool portOpen = port["port_open"].toBool();
    bool listening = port["listening"].toBool();
    
    if (portOpen && listening) {
      portLabel->setText("Port: ✅ 5055 is open and listening");
    } else if (portOpen) {
      portLabel->setText("Port: ⚠️ 5055 is open but not listening");
    } else {
      portLabel->setText("Port: ❌ 5055 is not accessible");
    }
  }
  
  // Dependencies status
  if (diagnostics.contains("dependencies")) {
    QJsonObject deps = diagnostics["dependencies"].toObject();
    bool depsOk = deps["dependencies_ok"].toBool();
    
    if (depsOk) {
      depsLabel->setText("Dependencies: ✅ All packages installed");
    } else {
      QJsonArray missing = deps["missing"].toArray();
      QStringList missingList;
      for (const QJsonValue &dep : missing) {
        missingList.append(dep.toString());
      }
      depsLabel->setText(QString("Dependencies: ❌ Missing: %1").arg(missingList.join(", ")));
    }
  }
  
  // Recent errors
  if (diagnostics.contains("logs")) {
    QString errorsText = formatErrors(diagnostics["logs"].toObject());
    errorsLabel->setText(errorsText);
  }
}

QString ConciergeStatusWidget::formatHealth(const QJsonObject &health) {
  QString status = health["status"].toString();
  int score = health["score"].toInt();
  int maxScore = health["max_score"].toInt();
  
  QString icon;
  QString color;
  QString explanation;
  
  if (status == "healthy") {
    icon = "✅";
    color = "#4CAF50";
    explanation = "All systems operational";
  } else if (status == "degraded") {
    icon = "⚠️";
    color = "#FF9800";
    explanation = "Some issues detected";
  } else {
    icon = "❌";
    color = "#FF6B6B";
    explanation = "Major issues - check details below";
  }
  
  QString text = QString("Health: %1 %2 (%3/%4) - %5").arg(icon, status.toUpper(), QString::number(score), QString::number(maxScore), explanation);
  healthLabel->setStyleSheet(QString("font-size: 40px; font-weight: 600; color: %1; margin-bottom: 20px;").arg(color));
  
  return text;
}

QString ConciergeStatusWidget::formatProcess(const QJsonObject &process) {
  bool running = process["running"].toBool();
  
  if (running) {
    int pid = process["pid"].toInt();
    double memoryMb = process["memory_mb"].toDouble();
    double cpuPercent = process["cpu_percent"].toDouble();
    return QString("Process: ✅ Running (PID %1, Memory: %2 MB, CPU: %3%)").arg(pid).arg(memoryMb, 0, 'f', 1).arg(cpuPercent, 0, 'f', 1);
  } else {
    QString error = process["error"].toString();
    if (!error.isEmpty()) {
      return QString("Process: ❌ Not Running - %1").arg(error);
    } else {
      return "Process: ❌ Not Running - Toggle above to start";
    }
  }
}

QString ConciergeStatusWidget::formatHttp(const QJsonObject &http) {
  bool responding = http["http_responding"].toBool();
  
  if (responding) {
    int statusCode = http["status_code"].toInt();
    double responseTime = http["response_time_ms"].toDouble();
    return QString("HTTP: ✅ Web server responding (Status: %1, Response time: %2ms)").arg(statusCode).arg(responseTime, 0, 'f', 0);
  } else {
    QString error = http["error"].toString();
    if (error == "Connection refused") {
      return "HTTP: ❌ Connection refused - Process may not be running";
    } else if (error == "Request timeout") {
      return "HTTP: ❌ Request timeout - Server may be overloaded";
    } else {
      return QString("HTTP: ❌ Error: %1").arg(error.isEmpty() ? "Unknown error" : error);
    }
  }
}

QString ConciergeStatusWidget::formatSystem(const QJsonObject &system) {
  // Not used anymore - resources aren't useful in this context
  return "";
}

QString ConciergeStatusWidget::formatErrors(const QJsonObject &logs) {
  QJsonArray errors = logs["recent_errors"].toArray();
  QJsonArray warnings = logs["recent_warnings"].toArray();
  
  QStringList messages;
  
  if (!errors.isEmpty()) {
    messages.append("❌ Recent Errors:");
    for (const QJsonValue &error : errors) {
      QString errorText = error.toString();
      if (!errorText.isEmpty()) {
        // Extract the most relevant part of the error
        if (errorText.contains("Traceback")) {
          messages.append("  • Python exception occurred (check logs)");
        } else if (errorText.contains("ImportError")) {
          messages.append("  • Missing Python module (check dependencies)");
        } else if (errorText.contains("Permission denied")) {
          messages.append("  • Permission error (may need sudo/restart)");
        } else if (errorText.contains("Address already in use")) {
          messages.append("  • Port 5055 already in use");
        } else {
          // Show shortened version
          if (errorText.length() > 100) {
            errorText = errorText.right(97) + "...";
          }
          messages.append(QString("  • %1").arg(errorText));
        }
      }
    }
  }
  
  if (!warnings.isEmpty() && errors.isEmpty()) {
    messages.append("⚠️ Recent Warnings:");
    for (const QJsonValue &warning : warnings) {
      QString warnText = warning.toString();
      if (!warnText.isEmpty() && warnText.length() > 60) {
        warnText = warnText.right(57) + "...";
      }
      messages.append(QString("  • %1").arg(warnText));
    }
  }
  
  if (messages.isEmpty()) {
    return "✅ No recent errors";
  }
  
  return messages.join("\n");
}

// Toggle Control Implementation
ConciergeToggleControl::ConciergeToggleControl() : ToggleControl("Concierge Web Server", "Enable the web-based management interface on port 5055", "") {
  // Initialize toggle state from params
  bool enabled = params.getBool("ConciergeEnabled");
  if (enabled != toggle.on) {
    toggle.togglePosition();
  }
  
  // Connect toggle changes
  QObject::connect(this, &ToggleControl::toggleFlipped, this, &ConciergeToggleControl::onToggleChanged);
}

void ConciergeToggleControl::onToggleChanged(bool enabled) {
  params.putBool("ConciergeEnabled", enabled);
  
  if (enabled) {
    // Set restart flag to trigger process restart
    params.putBool("RestartConcierge", true);
    
    // Also trigger a manager restart to ensure the process is restarted
    QProcess::execute("pkill", QStringList() << "-SIGHUP" << "manager");
  } else {
    // Set stop flag
    params.putBool("StopConcierge", true);
    
    // Kill the process directly to ensure it stops
    QProcess::execute("pkill", QStringList() << "-f" << "concierge.main");
  }
}

// Management Control Implementation
ConciergeManagementControl::ConciergeManagementControl(QWidget *parent) : QFrame(parent) {
  mainLayout = new QVBoxLayout(this);
  mainLayout->setSpacing(10);
  mainLayout->setMargin(0);
  
  // Add toggle control
  toggleControl = new ConciergeToggleControl();
  mainLayout->addWidget(toggleControl);
  
  // Add status widget
  statusWidget = new ConciergeStatusWidget();
  mainLayout->addWidget(statusWidget);
}

