#include "selfdrive/ui/qt/widgets/ssh_keys.h"

#include <QProcess>
#include <QMessageBox>

#include "common/params.h"
#include "selfdrive/ui/qt/api.h"
#include "selfdrive/ui/qt/widgets/input.h"

SshControl::SshControl() :
  ButtonControl(tr("SSH Keys"), "", tr("Warning: This grants SSH access to all public keys in your GitHub settings. Never enter a GitHub username "
                                       "other than your own. A comma employee will NEVER ask you to add their GitHub username.")) {

  QObject::connect(this, &ButtonControl::clicked, [=]() {
    if (text() == tr("ADD")) {
      QString username = InputDialog::getText(tr("Enter your GitHub username"), this);
      if (username.length() > 0) {
        setText(tr("LOADING"));
        setEnabled(false);
        getUserKeys(username);
      }
    } else {
      params.remove("GithubUsername");
      params_cache.remove("GithubUsername");
      params.remove("GithubSshKeys");
      params_cache.remove("GithubSshKeys");
      refresh();
    }
  });

  refresh();
}

void SshControl::refresh() {
  QString param = QString::fromStdString(params.get("GithubSshKeys"));
  if (param.length()) {
    setValue(QString::fromStdString(params.get("GithubUsername")));
    setText(tr("REMOVE"));
  } else {
    setValue("");
    setText(tr("ADD"));
  }
  setEnabled(true);
}

void SshControl::getUserKeys(const QString &username) {
  HttpRequest *request = new HttpRequest(this, false);
  QObject::connect(request, &HttpRequest::requestDone, [=](const QString &resp, bool success) {
    if (success) {
      if (!resp.isEmpty()) {
        params.put("GithubUsername", username.toStdString());
        params.put("GithubSshKeys", resp.toStdString());
      } else {
        ConfirmationDialog::alert(tr("Username '%1' has no keys on GitHub").arg(username), this);
      }
    } else {
      if (request->timeout()) {
        ConfirmationDialog::alert(tr("Request timed out"), this);
      } else {
        ConfirmationDialog::alert(tr("Username '%1' doesn't exist on GitHub").arg(username), this);
      }
    }

    refresh();
    request->deleteLater();
  });

  request->sendRequest("https://github.com/" + username + ".keys");
}

SshFixButton::SshFixButton() :
  ButtonControl(tr("Fix SSH Access"), tr("FIX SSH"), 
                tr("Restore SSH access by properly configuring the persistent SSH storage. "
                   "Use this if you're unable to SSH into your device after modifying AGNOS-level SSH settings.")) {
  
  QObject::connect(this, &ButtonControl::clicked, [=]() {
    setText(tr("FIXING..."));
    setEnabled(false);
    fixSshAccess();
  });
}

void SshFixButton::fixSshAccess() {
  // Run the simplified fix_ssh script with sudo (avoids Python version issues)
  QProcess process;
  process.start("sudo", QStringList() << "python3" << "/data/openpilot/selfdrive/ui/qt/network/fix_ssh_simple.py");
  
  if (!process.waitForFinished(30000)) { // 30 second timeout
    ConfirmationDialog::alert(tr("Failed to run SSH fix script: timeout"), this);
    setText(tr("FIX SSH"));
    setEnabled(true);
    return;
  }
  
  int exitCode = process.exitCode();
  QString output = process.readAllStandardOutput();
  QString error = process.readAllStandardError();
  
  if (exitCode == 0) {
    // Success
    QString message = tr("SSH access has been restored!\n\n");
    if (!output.isEmpty()) {
      // Extract just the success message
      QStringList lines = output.split('\n');
      for (const QString &line : lines) {
        if (line.startsWith("Success:")) {
          message += line.mid(8).trimmed();
          break;
        }
      }
    }
    message += tr("\n\nDetailed logs have been written to the Error Log.\n");
    message += tr("You can view them in: Settings -> Software -> Error Log");
    ConfirmationDialog::alert(message, this);
  } else {
    // Error - truncate long errors and point to error log
    QString errorMsg = tr("Failed to fix SSH access.\n\n");
    
    // Combine stderr and stdout for error detection
    QString fullOutput = error + "\n" + output;
    
    // Look for specific error patterns
    if (fullOutput.contains("Permission denied")) {
      errorMsg += tr("Permission denied error occurred.\n");
    } else if (fullOutput.contains("No module named")) {
      errorMsg += tr("Python module import error.\n");
    } else if (fullOutput.contains("Traceback")) {
      errorMsg += tr("Python script crashed with an exception.\n");
    } else {
      // Try to extract a meaningful error line
      QStringList lines = fullOutput.split('\n');
      for (const QString &line : lines) {
        if (line.contains("Error:") || line.contains("ERROR") || line.contains("Failed")) {
          errorMsg += line.trimmed() + "\n";
          break;
        }
      }
    }
    
    errorMsg += tr("\n** FULL ERROR DETAILS ARE IN THE ERROR LOG **\n");
    errorMsg += tr("\nTo see the complete error:\n");
    errorMsg += tr("Settings -> Software -> Error Log\n");
    errorMsg += tr("\nThe error log will show the full traceback and all details.");
    
    ConfirmationDialog::alert(errorMsg, this);
  }
  
  setText(tr("FIX SSH"));
  setEnabled(true);
}
