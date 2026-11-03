import sys
sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew
board_path = "/home/azzar/project/microcontrollers/03_projects/pids/pid-simple-controll/PCB/bldc_esp32_driver/bldc_esp32_driver.kicad_pcb"
board = pcbnew.LoadBoard(board_path)
ok = pcbnew.ExportSpecctraDSN(board, "/tmp/opencode/board.dsn")
print("export result:", ok)
