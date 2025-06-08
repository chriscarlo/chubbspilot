#include "selfdrive/frogpilot/utilities/concierge_status_widget.h"

#include <QDateTime>
#include <QDebug>

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
  mainLayout->setSpacing(8);
  mainLayout->setMargin(15);
  
  // Title
  titleLabel = new QLabel("Concierge Web Server Status", this);
  titleLabel->setStyleSheet("font-size: 18px; font-weight: bold; color: #E4E4E4; margin-bottom: 10px;");
  mainLayout->addWidget(titleLabel);
  
  // Health status
  healthLabel = new QLabel("Health: Checking...", this);
  healthLabel->setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 5px;");
  mainLayout->addWidget(healthLabel);
  
  // Process status
  processLabel = new QLabel("Process: Checking...", this);
  processLabel->setStyleSheet("font-size: 14px; color: #CCCCCC; margin-bottom: 3px;");
  mainLayout->addWidget(processLabel);
  
  // HTTP status
  httpLabel = new QLabel("HTTP: Checking...", this);
  httpLabel->setStyleSheet("font-size: 14px; color: #CCCCCC; margin-bottom: 3px;");
  mainLayout->addWidget(httpLabel);
  
  // System resources
  systemLabel = new QLabel("Resources: Checking...", this);
  systemLabel->setStyleSheet("font-size: 14px; color: #CCCCCC; margin-bottom: 3px;");
  mainLayout->addWidget(systemLabel);
  
  // Recent errors
  errorsLabel = new QLabel("", this);
  errorsLabel->setStyleSheet("font-size: 12px; color: #FF6B6B; margin-bottom: 5px;");
  errorsLabel->setWordWrap(true);
  mainLayout->addWidget(errorsLabel);
  
  // Last updated
  lastUpdatedLabel = new QLabel("Last updated: Never", this);
  lastUpdatedLabel->setStyleSheet("font-size: 11px; color: #888888; margin-top: 5px;");
  mainLayout->addWidget(lastUpdatedLabel);
  
  // Set frame style
  setFrameStyle(QFrame::Box);
  setStyleSheet("QFrame { background-color: #333333; border: 1px solid #555555; border-radius: 8px; }");
  setFixedHeight(220);
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
  
  // System resources
  if (diagnostics.contains("system")) {
    QString systemText = formatSystem(diagnostics["system"].toObject());
    systemLabel->setText(systemText);
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
  
  if (status == "healthy") {
    icon = "✅";
    color = "#4CAF50";
  } else if (status == "degraded") {
    icon = "⚠️";
    color = "#FF9800";
  } else {
    icon = "❌";
    color = "#FF6B6B";
  }
  
  QString text = QString("Health: %1 %2 (%3/%4)").arg(icon, status.toUpper(), QString::number(score), QString::number(maxScore));
  healthLabel->setStyleSheet(QString("font-size: 16px; font-weight: bold; color: %1; margin-bottom: 5px;").arg(color));
  
  return text;
}

QString ConciergeStatusWidget::formatProcess(const QJsonObject &process) {
  bool running = process["running"].toBool();
  
  if (running) {
    int pid = process["pid"].toInt();
    double memoryMb = process["memory_mb"].toDouble();
    return QString("Process: ✅ Running (PID %1, %2 MB)").arg(pid).arg(memoryMb, 0, 'f', 1);
  } else {
    return "Process: ❌ Not Running";
  }
}

QString ConciergeStatusWidget::formatHttp(const QJsonObject &http) {
  bool responding = http["http_responding"].toBool();
  
  if (responding) {
    int statusCode = http["status_code"].toInt();
    double responseTime = http["response_time_ms"].toDouble();
    return QString("HTTP: ✅ Port 5055 (%1, %2ms)").arg(statusCode).arg(responseTime, 0, 'f', 0);
  } else {
    QString error = http["error"].toString();
    return QString("HTTP: ❌ %1").arg(error.isEmpty() ? "Not Responding" : error);
  }
}

QString ConciergeStatusWidget::formatSystem(const QJsonObject &system) {
  if (system.contains("error")) {
    return "Resources: ❌ Error checking";
  }
  
  double memoryAvailMb = system["memory_available_mb"].toDouble();
  double diskFreeGb = system["disk_free_gb"].toDouble();
  bool networkUp = system["network_up"].toBool();
  
  QString networkIcon = networkUp ? "✅" : "❌";
  
  return QString("Resources: %1 Net, %2GB disk, %3MB RAM")
         .arg(networkIcon)
         .arg(diskFreeGb, 0, 'f', 1)
         .arg(memoryAvailMb, 0, 'f', 0);
}

QString ConciergeStatusWidget::formatErrors(const QJsonObject &logs) {
  QJsonArray errors = logs["recent_errors"].toArray();
  
  if (errors.isEmpty()) {
    return "";
  }
  
  QStringList errorList;
  for (const QJsonValue &error : errors) {
    QString errorText = error.toString();
    if (!errorText.isEmpty()) {
      // Truncate long error messages
      if (errorText.length() > 80) {
        errorText = errorText.left(77) + "...";
      }
      errorList.append(errorText);
    }
  }
  
  if (!errorList.isEmpty()) {
    return QString("Recent Errors:\n%1").arg(errorList.join("\n"));
  }
  
  return "";
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
    // Restart concierge service through params
    params.putBool("RestartConcierge", true);
  } else {
    // Stop concierge service
    params.putBool("StopConcierge", true);
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

#include "concierge_status_widget.moc"