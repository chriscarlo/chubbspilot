#pragma once

#include <string>
#include <vector>
#include <map>
#include <mutex>
#include <chrono>

// Terminal colors using ANSI escape codes
#define COLOR_RESET   "\033[0m"
#define COLOR_BLACK   "\033[30m"
#define COLOR_RED     "\033[31m"
#define COLOR_GREEN   "\033[32m"
#define COLOR_YELLOW  "\033[33m"
#define COLOR_BLUE    "\033[34m"
#define COLOR_MAGENTA "\033[35m"
#define COLOR_CYAN    "\033[36m"
#define COLOR_WHITE   "\033[37m"
#define COLOR_SALMON  "\033[38;2;255;105;105m"  // Our custom salmon-red

// Background colors
#define BG_BLACK      "\033[40m"

// Text styles
#define STYLE_BOLD    "\033[1m"
#define STYLE_DIM     "\033[2m"
#define COLOR_DIM     "\033[2m"  // Alias for compatibility

// Clear screen and cursor control
#define CLEAR_SCREEN  "\033[2J"
#define CURSOR_HOME   "\033[H"
#define HIDE_CURSOR   "\033[?25l"
#define SHOW_CURSOR   "\033[?25h"

enum class ServiceStatus {
  PENDING,
  STARTING,
  RUNNING,
  FAILED
};

struct ServiceInfo {
  std::string name;
  std::string display_name;
  ServiceStatus status;
  std::string message;
  std::string error_details;  // Full error info
  std::string error_file;     // File where error occurred
  int error_line;             // Line number
  std::string suggested_fix;  // Actionable advice
};

class TerminalBootUI {
public:
  TerminalBootUI();
  ~TerminalBootUI();

  void init();
  void update(const std::string& input);
  void render();
  
  // Service management
  void updateService(const std::string& name, ServiceStatus status, const std::string& message = "");
  void setProgress(int percentage);
  void setPhase(const std::string& phase);
  
private:
  void drawHeader();
  void drawSystemInfo();
  void drawServices();
  void drawProgress();
  void drawFooter();
  void drawErrors();  // New error display section
  
  std::string getStatusSymbol(ServiceStatus status);
  std::string getStatusColor(ServiceStatus status);
  bool hasErrors();
  
  std::mutex update_mutex;
  std::map<std::string, ServiceInfo> services;
  int progress_percentage;
  std::string current_phase;
  
  // System info
  std::string platform;
  std::string serial;
  std::string imei;
  
  // Timing
  std::chrono::steady_clock::time_point boot_start;
};