#include <regex>

#include <QtConcurrent>

#include <QProcess>

#include "selfdrive/frogpilot/navigation/ui/maps_settings.h"

FrogPilotMapsPanel::FrogPilotMapsPanel(FrogPilotSettingsWindow *parent) : FrogPilotListWidget(parent), parent(parent), mapsFolderPath{"/data/media/0/osm/offline"} {
  QVBoxLayout *mainLayout = new QVBoxLayout();
  addItem(mainLayout);

  mapsLayout = new QStackedLayout();
  mainLayout->addLayout(mapsLayout);

  FrogPilotListWidget *settingsList = new FrogPilotListWidget(this);

  std::vector<QString> scheduleOptions{tr("Manually"), tr("Weekly"), tr("Monthly")};
  ButtonParamControl *preferredSchedule = new ButtonParamControl("PreferredSchedule", tr("Automatically Update Maps"),
                                          tr("Controls the frequency at which maps update with the latest OpenStreetMap (OSM) changes. "
                                             "Weekly updates begin at midnight every Sunday, while monthly updates start at midnight on the 1st of each month."),
                                             "",
                                             scheduleOptions);
  settingsList->addItem(preferredSchedule);

  FrogPilotButtonsControl *selectMaps = new FrogPilotButtonsControl(tr("Select Map Data Sources"),
                                                                    tr("Select map data sources to use with 'Curve Speed Control' and 'Speed Limit Controller'."),
                                                                    "", {tr("COUNTRIES"), tr("STATES")});
  QObject::connect(selectMaps, &FrogPilotButtonsControl::buttonClicked, [this](int id) {
    mapsLayout->setCurrentIndex(id + 1);
    openMapSelection();
  });
  settingsList->addItem(selectMaps);

  downloadMapsButton = new ButtonControl(tr("Download Maps"), tr("DOWNLOAD"), tr("Downloads the selected maps to use with 'Curve Speed Control' and 'Speed Limit Controller'."));
  QObject::connect(downloadMapsButton, &ButtonControl::clicked, [this] {
    if (downloadMapsButton->text() == tr("CANCEL")) {
      if (FrogPilotConfirmationDialog::yesorno(tr("Are you sure you want to cancel the download?"), this)) {
        cancelDownload();
      }
    } else {
      startDownload();
    }
  });
  settingsList->addItem(downloadMapsButton);

  settingsList->addItem(downloadETA = new LabelControl(tr("Download Completion ETA")));
  settingsList->addItem(downloadStatus = new LabelControl(tr("Download Progress")));
  settingsList->addItem(downloadTimeElapsed = new LabelControl(tr("Download Time Elapsed")));
  settingsList->addItem(lastMapsDownload = new LabelControl(tr("Maps Last Updated"), params.get("LastMapsUpdate").empty() ? "Never" : QString::fromStdString(params.get("LastMapsUpdate"))));
  settingsList->addItem(mapsSize = new LabelControl(tr("Downloaded Maps Size"), calculateDirectorySize(mapsFolderPath)));

  downloadETA->setVisible(false);
  downloadStatus->setVisible(false);
  downloadTimeElapsed->setVisible(false);

  removeMapsButton = new ButtonControl(tr("Remove Maps"), tr("REMOVE"), tr("Removes downloaded maps to clear up storage space."));
  QObject::connect(removeMapsButton, &ButtonControl::clicked, [this] {
    if (FrogPilotConfirmationDialog::yesorno(tr("Are you sure you want to delete all of your downloaded maps?"), this)) {
      std::thread([this] {
        mapsSize->setText("0 MB");

        std::system("rm -rf /data/media/0/osm/offline");
      }).detach();
    }
  });
  settingsList->addItem(removeMapsButton);

  ScrollView *settingsPanel = new ScrollView(settingsList, this);
  mapsLayout->addWidget(settingsPanel);

  FrogPilotListWidget *countriesList = new FrogPilotListWidget(this);
  std::vector<std::pair<QString, QMap<QString, QString>>> countries = {
    {tr("Africa"), africaMap},
    {tr("Antarctica"), antarcticaMap},
    {tr("Asia"), asiaMap},
    {tr("Europe"), europeMap},
    {tr("North America"), northAmericaMap},
    {tr("Oceania"), oceaniaMap},
    {tr("South America"), southAmericaMap}
  };

  for (std::pair<QString, QMap<QString, QString>> country : countries) {
    countriesList->addItem(new LabelControl(country.first, ""));
    countriesList->addItem(new MapSelectionControl(country.second, true));
  }

  ScrollView *countryMapsPanel = new ScrollView(countriesList, this);
  mapsLayout->addWidget(countryMapsPanel);

  FrogPilotListWidget *statesList = new FrogPilotListWidget(this);
  std::vector<std::pair<QString, QMap<QString, QString>>> states = {
    {tr("United States - Midwest"), midwestMap},
    {tr("United States - Northeast"), northeastMap},
    {tr("United States - South"), southMap},
    {tr("United States - West"), westMap},
    {tr("United States - Territories"), territoriesMap}
  };

  for (std::pair<QString, QMap<QString, QString>> state : states) {
    statesList->addItem(new LabelControl(state.first, ""));
    statesList->addItem(new MapSelectionControl(state.second));
  }

  ScrollView *stateMapsPanel = new ScrollView(statesList, this);
  mapsLayout->addWidget(stateMapsPanel);

  QObject::connect(parent, &FrogPilotSettingsWindow::closeMapSelection, [this] {
    std::string mapsSelected = params.get("MapsSelected");
    hasMapsSelected = !QJsonDocument::fromJson(QByteArray::fromStdString(mapsSelected)).object().value("nations").toArray().isEmpty();
    hasMapsSelected |= !QJsonDocument::fromJson(QByteArray::fromStdString(mapsSelected)).object().value("states").toArray().isEmpty();

    mapsLayout->setCurrentIndex(0);
  });
  QObject::connect(uiState(), &UIState::uiUpdate, this, &FrogPilotMapsPanel::updateState);
}

void FrogPilotMapsPanel::showEvent(QShowEvent *event) {
  std::string mapsSelected = params.get("MapsSelected");
  hasMapsSelected = !QJsonDocument::fromJson(QByteArray::fromStdString(mapsSelected)).object().value("nations").toArray().isEmpty();
  hasMapsSelected |= !QJsonDocument::fromJson(QByteArray::fromStdString(mapsSelected)).object().value("states").toArray().isEmpty();

  removeMapsButton->setVisible(QDir(mapsFolderPath).exists());

  std::string osmDownloadProgress = params.get("OSMDownloadProgress");
  if (!osmDownloadProgress.empty()) {
    downloadMapsButton->setText(tr("CANCEL"));
    downloadStatus->setText("Calculating...");

    downloadStatus->setVisible(true);

    lastMapsDownload->setVisible(false);
    removeMapsButton->setVisible(false);

    updateDownloadLabels(osmDownloadProgress);
  }
}


void FrogPilotMapsPanel::updateState(const UIState &s) {
  if (!isVisible() || s.sm->frame % (UI_FREQ / 2) != 0) {
    return;
  }

  downloadMapsButton->setEnabled(!cancellingDownload && hasMapsSelected && s.scene.online);

  std::string osmDownloadProgress = params.get("OSMDownloadProgress");
  if (!osmDownloadProgress.empty() && !cancellingDownload) {
    updateDownloadLabels(osmDownloadProgress);
  }

  parent->keepScreenOn = !osmDownloadProgress.empty();
}

void FrogPilotMapsPanel::cancelDownload() {
  cancellingDownload = true;

  downloadMapsButton->setEnabled(false);

  downloadETA->setText("Cancelling...");
  downloadMapsButton->setText(tr("CANCELLED"));
  downloadStatus->setText("Cancelling...");
  downloadTimeElapsed->setText("Cancelling...");

  params_memory.putBool("OSMCancelDownload", true);

  params.remove("OSMDownloadProgress");

  QDateTime cancelStartTime = QDateTime::currentDateTime();

  QTimer::singleShot(2500, [this, cancelStartTime]() {
    std::string progress = params.get("OSMDownloadProgress");
    bool scriptLikelyFinished = !progress.empty();

    cancellingDownload = false;
    downloadMapsButton->setEnabled(true);

    if (!scriptLikelyFinished) {
      downloadMapsButton->setText(tr("DOWNLOAD"));
      downloadETA->setVisible(false);
      downloadStatus->setVisible(false);
      downloadTimeElapsed->setVisible(false);
      lastMapsDownload->setVisible(true);
      removeMapsButton->setVisible(QDir(mapsFolderPath).exists());
    } else {
      update();
    }

    params_memory.remove("OSMCancelDownload");

    update();
  });
}

void FrogPilotMapsPanel::startDownload() {
  params_memory.remove("OSMCancelDownload");

  downloadETA->setText("Starting...");
  downloadMapsButton->setText(tr("CANCEL"));
  downloadStatus->setText("Starting...");
  downloadTimeElapsed->setText("00:00:00");

  downloadETA->setVisible(true);
  downloadStatus->setVisible(true);
  downloadTimeElapsed->setVisible(true);

  lastMapsDownload->setVisible(false);
  removeMapsButton->setVisible(false);

  elapsedTime.start();
  startTime = QDateTime::currentDateTime();

  params_memory.put("OSMDownloadLocations", params.get("MapsSelected"));

  QString program = "python";
  QStringList arguments;
  arguments << "-m" << "selfdrive.frogpilot.navigation.mapd_py.downloader.downloader";

  QProcess *process = new QProcess(this);
  process->setProcessChannelMode(QProcess::MergedChannels);

  connect(process, &QProcess::readyReadStandardOutput, [=]() {
      qDebug() << process->readAllStandardOutput();
  });
  connect(process, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
          [=](int exitCode, QProcess::ExitStatus exitStatus) {
      qDebug() << "Downloader script finished with code" << exitCode << "status" << exitStatus;
      process->deleteLater();
  });

  qDebug() << "Starting downloader script:" << program << arguments;
  process->start(program, arguments);

  if (!process->waitForStarted(5000)) {
      qCritical() << "Failed to start downloader script!";
      QJsonObject errorProgress;
      errorProgress["current_action"] = "Error";
      errorProgress["error_message"] = "Failed to start downloader process.";
      errorProgress["total_files"] = 0;
      errorProgress["downloaded_files"] = 0;
      errorProgress["locations_to_download"] = QJsonArray();
      errorProgress["location_details"] = QJsonObject();
      QJsonDocument doc(errorProgress);
      params.put("OSMDownloadProgress", doc.toJson(QJsonDocument::Compact).toStdString());

      downloadMapsButton->setText(tr("ERROR"));
      downloadMapsButton->setEnabled(false);
  } else {
      qDebug() << "Downloader script started successfully.";
  }
}

void FrogPilotMapsPanel::updateDownloadLabels(std::string &osmDownloadProgress) {
  QJsonDocument doc = QJsonDocument::fromJson(QByteArray::fromStdString(osmDownloadProgress));
  QJsonObject progressJson = doc.object();

  if (progressJson.isEmpty()) {
    return;
  }

  int totalFiles = progressJson.value("total_files").toInt(0);
  int downloadedFiles = progressJson.value("downloaded_files").toInt(0);
  QString currentAction = progressJson.value("current_action").toString("Idle");
  QString errorMessage = progressJson.value("error_message").toString("");

  if (currentAction == "Error" || !errorMessage.isEmpty()) {
      downloadMapsButton->setText(tr("ERROR"));
      downloadStatus->setText(tr("Error: %1").arg(errorMessage.isEmpty() ? "Unknown download error" : errorMessage));
      downloadETA->setVisible(false);
      downloadTimeElapsed->setVisible(false);
      lastMapsDownload->setVisible(true);
      removeMapsButton->setVisible(QDir(mapsFolderPath).exists());
      params.remove("OSMDownloadProgress");
      downloadMapsButton->setEnabled(false);
      update();
      return;
  }

  if (currentAction == "Complete" || (totalFiles > 0 && downloadedFiles == totalFiles)) {
    downloadMapsButton->setText(tr("DOWNLOAD"));
    lastMapsDownload->setText(formatCurrentDate());

    downloadETA->setVisible(false);
    downloadStatus->setVisible(false);
    downloadTimeElapsed->setVisible(false);

    lastMapsDownload->setVisible(true);
    removeMapsButton->setVisible(true);

    params.put("LastMapsUpdate", formatCurrentDate().toStdString());
    params.remove("OSMDownloadProgress");

    std::thread([this]() { mapsSize->setText(calculateDirectorySize(mapsFolderPath)); }).detach();

    update();
    return;
  }

  if (totalFiles > 0 && downloadedFiles >= 0 && downloadedFiles < totalFiles) {
      downloadMapsButton->setText(tr("CANCEL"));

      static int previousDownloadedFiles = -1;
      if (downloadedFiles != previousDownloadedFiles) {
        if (downloadedFiles % 5 == 0 || previousDownloadedFiles == -1) {
            std::thread([this]() {
                mapsSize->setText(calculateDirectorySize(mapsFolderPath));
            }).detach();
        }
        previousDownloadedFiles = downloadedFiles;
      }

      downloadETA->setText(QString("%1").arg(formatETA(elapsedTime.elapsed(), downloadedFiles, previousDownloadedFiles, totalFiles, startTime)));
      downloadStatus->setText(tr("%1 / %2 files (%3%) - %4")
                                  .arg(downloadedFiles)
                                  .arg(totalFiles)
                                  .arg(totalFiles > 0 ? (downloadedFiles * 100) / totalFiles : 0)
                                  .arg(currentAction));
      downloadTimeElapsed->setText(formatElapsedTime(elapsedTime.elapsed()));

      downloadETA->setVisible(true);
      downloadStatus->setVisible(true);
      downloadTimeElapsed->setVisible(true);
      lastMapsDownload->setVisible(false);
      removeMapsButton->setVisible(false);

  } else if (currentAction == "Starting" || currentAction == "Idle" || currentAction == "Calculating") {
      downloadMapsButton->setText(tr("CANCEL"));
      downloadStatus->setText(tr(currentAction.toStdString().c_str()));
      downloadETA->setVisible(true);
      downloadETA->setText("Calculating...");
      downloadTimeElapsed->setVisible(true);
      downloadTimeElapsed->setText("00:00:00");
      lastMapsDownload->setVisible(false);
      removeMapsButton->setVisible(false);
  } else {
  }
}
