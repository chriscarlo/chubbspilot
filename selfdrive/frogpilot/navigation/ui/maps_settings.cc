#include <regex>

#include <QtConcurrent>

#include "selfdrive/frogpilot/navigation/ui/maps_settings.h"

FrogPilotMapsPanel::FrogPilotMapsPanel(FrogPilotSettingsWindow *parent) : FrogPilotListWidget(parent), parent(parent), mapsFolderPath{"/data/media/0/osm/offline"} {
  QVBoxLayout *mainLayout = new QVBoxLayout();
  addItem(mainLayout);

  FrogPilotListWidget *settingsList = new FrogPilotListWidget(this);
  mainLayout->addWidget(new ScrollView(settingsList, this));

  ButtonControl *downloadCaliforniaButton = new ButtonControl(tr("Download California Map"), tr("DOWNLOAD"));
  QObject::connect(downloadCaliforniaButton, &ButtonControl::clicked, [this] {
    params.putNonBlocking("MapsSelected", "california");
    downloadCaliforniaButton->setText(tr("REQUEST SENT"));
    QTimer::singleShot(2000, [downloadCaliforniaButton]() { downloadCaliforniaButton->setText(tr("DOWNLOAD")); });
    ConfirmationDialog::alert(tr("Request sent to download California map data. Monitor progress via logs or future UI element."), this);
  });
  settingsList->addItem(downloadCaliforniaButton);

  ButtonControl *downloadNevadaButton = new ButtonControl(tr("Download Nevada Map"), tr("DOWNLOAD"));
  QObject::connect(downloadNevadaButton, &ButtonControl::clicked, [this] {
    params.putNonBlocking("MapsSelected", "nevada");
    downloadNevadaButton->setText(tr("REQUEST SENT"));
    QTimer::singleShot(2000, [downloadNevadaButton]() { downloadNevadaButton->setText(tr("DOWNLOAD")); });
    ConfirmationDialog::alert(tr("Request sent to download Nevada map data. Monitor progress via logs or future UI element."), this);
  });
  settingsList->addItem(downloadNevadaButton);

  settingsList->addItem(lastMapsDownload = new LabelControl(tr("Maps Last Updated"), params.get("LastMapsUpdate").empty() ? "Never" : QString::fromStdString(params.get("LastMapsUpdate"))));
  mapsFolderPath = "/data/media/0/map_data_tiles_protobuf/";
  settingsList->addItem(mapsSize = new LabelControl(tr("Downloaded Maps Size"), calculateDirectorySize(mapsFolderPath)));

  QObject::connect(parent, &FrogPilotSettingsWindow::closeMapSelection, [this] {
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

QString FrogPilotMapsPanel::calculateDirectorySize(const QString &directoryPath) {
  QDir directory(directoryPath);
  if (!directory.exists()) {
    return "0 MB";
  }

  quint64 totalSize = 0;
  QFileInfoList fileList = directory.entryInfoList(QDir::Files | QDir::Dirs | QDir::NoDotAndDotDot | QDir::Hidden | QDir::System);

  for (const QFileInfo &fileInfo : fileList) {
    if (fileInfo.isDir()) {
    } else {
      totalSize += fileInfo.size();
    }
  }

  double sizeMB = static_cast<double>(totalSize) / (1024 * 1024);
  return QString::number(sizeMB, 'f', 2) + " MB";
}

QString FrogPilotMapsPanel::formatCurrentDate() {
    return QDateTime::currentDateTime().toString("MMMM d, yyyy");
}
