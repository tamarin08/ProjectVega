"""Independent Windows application; shared Titan and MIDI modules are bundled."""

from pathlib import Path
import sys
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
)

root = Path(SPECPATH).parent
sys.path.insert(0,str(root / "src"))
from edmond import __version__
version_tuple = tuple(int(part) for part in __version__.split(".")) + (0,)
version = VSVersionInfo(
    ffi=FixedFileInfo(filevers=version_tuple,prodvers=version_tuple,mask=0x3F,flags=0,OS=0x40004,fileType=1,subtype=0,date=(0,0)),
    kids=[StringFileInfo([StringTable("040904B0",[
        StringStruct("ProductName","Project Edmond"),StringStruct("FileDescription","Edmond MPC Beats Controller"),
        StringStruct("FileVersion",__version__),StringStruct("ProductVersion",__version__),
        StringStruct("InternalName","Edmond"),StringStruct("OriginalFilename","Edmond.exe"),
    ])]),VarFileInfo([VarStruct("Translation",[1033,1200])])],
)
icon = root / "src" / "edmond" / "resources" / "edmond.ico"
a = Analysis([str(root / "packaging" / "edmond-entry.py")],pathex=[str(root / "src")],
    datas=[(str(icon),"edmond/resources")],hiddenimports=["mido.backends.rtmidi","pygame.midi"],
    excludes=["pytest","unittest","pygame.tests","pygame.examples","tkinter"],noarchive=False)
unused = {"qpdf.dll","qtvirtualkeyboardplugin.dll","Qt6Pdf.dll","Qt6VirtualKeyboard.dll",
          "Qt6Qml.dll","Qt6QmlMeta.dll","Qt6QmlModels.dll","Qt6QmlWorkerScript.dll","Qt6Quick.dll"}
a.binaries = [entry for entry in a.binaries if Path(entry[0]).name not in unused]
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name="Edmond",console=False,icon=str(icon),version=version,upx=False)
coll = COLLECT(exe,a.binaries,a.datas,name="Edmond",upx=False)
