from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def main() -> None:
    if getattr(sys, 'frozen', False):
        app_dir = Path(sys.executable).resolve().parent
    else:
        app_dir = Path(__file__).resolve().parent.parent
    update_dir = app_dir / 'update'
    update_exe = update_dir / 'AREZONE.exe'
    target_exe = app_dir / 'AREZONE.exe'
    if not update_exe.exists():
        print('No hay actualización disponible.')
        return
    if target_exe.exists() and target_exe.resolve() != update_exe.resolve():
        target_exe.unlink(missing_ok=True)
    shutil.copy2(update_exe, target_exe)
    update_exe.unlink(missing_ok=True)
    try:
        os.rmdir(update_dir)
    except OSError:
        pass
    print('Actualización aplicada correctamente.')


if __name__ == '__main__':
    main()
