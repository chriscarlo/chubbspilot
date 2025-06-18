#pragma once

#include "selfdrive/frogpilot/navigation/ui/navigation_functions.h"
#include "selfdrive/frogpilot/ui/qt/offroad/frogpilot_settings.h"
#include "common/params.h"
#include "selfdrive/ui/qt/util.h"

class FrogPilotMapsPanel : public FrogPilotListWidget {
  Q_OBJECT

public:
  explicit FrogPilotMapsPanel(FrogPilotSettingsWindow *parent);

signals:
  void openMapSelection();

protected:
  void showEvent(QShowEvent *event) override;

private:
  void cancelDownload();
  void startDownload();
  void updateDownloadLabels(std::string &osmDownloadProgress);
  void updateState(const UIState &s);
  QString calculateDirectorySize(const QString &directoryPath);
  QString formatCurrentDate();

  bool cancellingDownload;
  bool hasMapsSelected;

  ButtonControl *downloadCaliforniaButton;
  ButtonControl *downloadMapsButton;
  ButtonControl *removeMapsButton;
  ParamWatcher *trigger_param_watcher;

  FrogPilotSettingsWindow *parent;

  LabelControl *downloadETA;
  LabelControl *downloadStatus;
  LabelControl *downloadTimeElapsed;
  LabelControl *lastMapsDownload;
  LabelControl *mapsSize;

  Params params;
  Params params_memory{"/dev/shm/params"};

  ParamWatcher *download_complete_watcher;

  QDateTime startTime;

  QElapsedTimer elapsedTime;

  QString mapsFolderPath;

  const QString MAPS_PATH = "/data/media/0/map_data_tiles_protobuf/";

  QStackedLayout *mapsLayout;

private slots:
  void updateButtonStates();
  void handleDownloadComplete();
};
