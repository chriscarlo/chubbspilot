#include <QDirIterator>
#include <regex>

#include <QtConcurrent>

#include "selfdrive/frogpilot/navigation/ui/maps_settings.h"

FrogPilotMapsPanel::FrogPilotMapsPanel(FrogPilotSettingsWindow *parent) : FrogPilotListWidget(parent), parent(parent) {
  QVBoxLayout *mainLayout = new QVBoxLayout();
  addItem(mainLayout);

  FrogPilotListWidget *settingsList = new FrogPilotListWidget(this);
  mainLayout->addWidget(new ScrollView(settingsList, this));

  ButtonControl *downloadCaliforniaButton = new ButtonControl(tr("Download California Map"), tr("DOWNLOAD"));
  QObject::connect(downloadCaliforniaButton, &ButtonControl::clicked, [this, downloadCaliforniaButton] {
    params.remove("LastMapsUpdate");
    downloadCaliforniaButton->setText(tr("UPDATE REQUESTED"));
    QTimer::singleShot(5000, [downloadCaliforniaButton]() { downloadCaliforniaButton->setText(tr("DOWNLOAD")); });
    ConfirmationDialog::alert(tr("Request sent to check for map updates. Update will occur according to schedule (daily, weekly, or monthly) or on next boot."), this);
  });
  settingsList->addItem(downloadCaliforniaButton);

  ButtonControl *downloadNevadaButton = new ButtonControl(tr("Download Nevada Map"), tr("DOWNLOAD"));
  QObject::connect(downloadNevadaButton, &ButtonControl::clicked, [this, downloadNevadaButton] {
    params.remove("LastMapsUpdate");
    downloadNevadaButton->setText(tr("UPDATE REQUESTED"));
    QTimer::singleShot(5000, [downloadNevadaButton]() { downloadNevadaButton->setText(tr("DOWNLOAD")); });
    ConfirmationDialog::alert(tr("Request sent to check for map updates. Update will occur according to schedule (daily, weekly, or monthly) or on next boot."), this);
  });
  settingsList->addItem(downloadNevadaButton);

  const QString mapsPath = "/data/media/0/map_data_tiles_protobuf/";
  settingsList->addItem(lastMapsDownload = new LabelControl(tr("Maps Last Updated"), params.get("LastMapsUpdate").empty() ? "Never" : QString::fromStdString(params.get("LastMapsUpdate"))));
  settingsList->addItem(mapsSize = new LabelControl(tr("Downloaded Maps Size"), calculateDirectorySize(mapsPath)));

  QObject::connect(parent, &FrogPilotSettingsWindow::closeMapSelection, [] {
  });
  QObject::connect(uiState(), &UIState::uiUpdate, this, &FrogPilotMapsPanel::updateState);
}

void FrogPilotMapsPanel::showEvent(QShowEvent *event) {
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
