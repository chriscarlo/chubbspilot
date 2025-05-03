#include <QDirIterator>
#include <regex>
#include <QColor>
#include <QStyle>

#include <QtConcurrent>

#include "selfdrive/frogpilot/navigation/ui/maps_settings.h"
#include "common/params.h"
#include "selfdrive/ui/qt/util.h"
#include "selfdrive/ui/qt/widgets/input.h"

FrogPilotMapsPanel::FrogPilotMapsPanel(FrogPilotSettingsWindow *parent) : FrogPilotListWidget(parent), parent(parent) {
  QVBoxLayout *mainLayout = new QVBoxLayout();
  addItem(mainLayout);

  FrogPilotListWidget *settingsList = new FrogPilotListWidget(this);
  mainLayout->addWidget(new ScrollView(settingsList, this));

  downloadCaliforniaButton = new ButtonControl(tr("Download California Map"), tr("DOWNLOAD"));
  downloadCaliforniaButton->setProperty("downloading", false);
  downloadCaliforniaButton->setObjectName("californiaDownloadBtn");

  QObject::connect(downloadCaliforniaButton, &ButtonControl::clicked, [this] {
    params_memory.putBoolNonBlocking("TriggerMapDownloadCheck", true);
  });
  settingsList->addItem(downloadCaliforniaButton);

  downloadMapsButton = new ButtonControl(tr("Download Nevada Map"), tr("DOWNLOAD"));
  QObject::connect(downloadMapsButton, &ButtonControl::clicked, [this] {
    params_memory.putBoolNonBlocking("TriggerMapDownloadCheck", true);
  });
  settingsList->addItem(downloadMapsButton);

  const QString mapsPath = "/data/media/0/map_data_tiles_protobuf/";
  settingsList->addItem(lastMapsDownload = new LabelControl(tr("Maps Last Updated"), params.get("LastMapsUpdate").empty() ? "Never" : QString::fromStdString(params.get("LastMapsUpdate"))));
  settingsList->addItem(mapsSize = new LabelControl(tr("Downloaded Maps Size"), calculateDirectorySize(mapsPath)));

  trigger_param_watcher = new ParamWatcher(this);
  QObject::connect(trigger_param_watcher, &ParamWatcher::paramChanged, this, &FrogPilotMapsPanel::updateButtonStates);
  trigger_param_watcher->addParam("TriggerMapDownloadCheck");

  // Watch for download completion
  download_complete_watcher = new ParamWatcher(this);
  QObject::connect(download_complete_watcher, &ParamWatcher::paramChanged, this, &FrogPilotMapsPanel::handleDownloadComplete);
  download_complete_watcher->addParam("MapDownloadComplete");

  QString styleSheet = R"(
    #californiaDownloadBtn[downloading="true"] {
      background-color: blue;
    }
  )";
  setStyleSheet(styleSheet);

  updateButtonStates();

  QObject::connect(parent, &FrogPilotSettingsWindow::closeMapSelection, [] {
  });
  QObject::connect(uiState(), &UIState::uiUpdate, this, &FrogPilotMapsPanel::updateState);
}

void FrogPilotMapsPanel::handleDownloadComplete() {
  if (params_memory.getBool("MapDownloadComplete")) {
    mapsSize->setText(calculateDirectorySize(MAPS_PATH));
    lastMapsDownload->setText(formatCurrentDate());
    params.put("LastMapsUpdate", formatCurrentDate().toStdString());
    // Reset the trigger
    params_memory.putBool("MapDownloadComplete", false);
  }
}

void FrogPilotMapsPanel::updateButtonStates() {
  bool isTriggerSet = params_memory.getBool("TriggerMapDownloadCheck");
  if (downloadCaliforniaButton) {
    bool currentDownloadingState = downloadCaliforniaButton->property("downloading").toBool();
    if (currentDownloadingState != isTriggerSet) {
        downloadCaliforniaButton->setProperty("downloading", isTriggerSet);
        downloadCaliforniaButton->style()->unpolish(downloadCaliforniaButton);
        downloadCaliforniaButton->style()->polish(downloadCaliforniaButton);
    }
  }
}

void FrogPilotMapsPanel::showEvent(QShowEvent *event) {
  updateButtonStates();
}

void FrogPilotMapsPanel::updateState(const UIState &s) {
  if (!isVisible() || s.sm->frame % (UI_FREQ / 2) != 0) {
    return;
  }
}

quint64 calculate_total_size(const QString &directoryPath) {
  quint64 totalSize = 0;
  QDirIterator it(directoryPath, QDir::Files | QDir::Dirs | QDir::NoDotAndDotDot | QDir::Hidden | QDir::System, QDirIterator::Subdirectories);
  while (it.hasNext()) {
    it.next();
    QFileInfo fileInfo = it.fileInfo();
    if (fileInfo.isFile()) {
      totalSize += fileInfo.size();
    }
  }
  return totalSize;
}

QString FrogPilotMapsPanel::calculateDirectorySize(const QString &directoryPath) {
  QDir directory(directoryPath);
  if (!directory.exists()) {
    return "0 MB";
  }

  quint64 totalSize = calculate_total_size(directoryPath);

  double sizeMB = static_cast<double>(totalSize) / (1024 * 1024);
  if (sizeMB < 1.0) {
     double sizeKB = static_cast<double>(totalSize) / 1024;
     return QString::number(sizeKB, 'f', 2) + " KB";
  } else if (sizeMB < 1024.0) {
    return QString::number(sizeMB, 'f', 2) + " MB";
  } else {
    double sizeGB = sizeMB / 1024;
    return QString::number(sizeGB, 'f', 2) + " GB";
  }
}

QString FrogPilotMapsPanel::formatCurrentDate() {
    return QDateTime::currentDateTime().toString("MMMM d, yyyy");
}
