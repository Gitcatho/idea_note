"""Build local macOS bundle without publishing or developer account access."""
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import plistlib
import subprocess
import sys
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parent
os.environ['PYINSTALLER_CONFIG_DIR']=str(ROOT/'build'/'cache')
stage=ROOT/'build'/'resources';stage.mkdir(parents=True,exist_ok=True)
image=Image.new('RGBA',(1024,1024));draw=ImageDraw.Draw(image)
draw.rounded_rectangle((0,0,1023,1023),radius=210,fill='#4b57d6')
draw.line([(290,740),(290,280),(720,740),(720,280)],fill='white',width=90,joint='curve')
image.save(stage/'app.icns')
licenses=stage/'licenses';licenses.mkdir(exist_ok=True)
packages=[]
for name in ['pywebview','pyinstaller','proxy_tools','bottle','typing_extensions','pyobjc-core','pyobjc-framework-Cocoa','pyobjc-framework-WebKit']:
 try:d=importlib.metadata.distribution(name)
 except importlib.metadata.PackageNotFoundError:continue
 packages.append({'name':name,'version':d.version,'license':d.metadata.get('License')})
 for entry in d.files or []:
  if entry.name.lower().startswith(('license','copying','notice')) and '.dist-info' in str(entry):
   p=Path(d.locate_file(entry))
   if p.is_file():(licenses/(name+'-'+entry.name)).write_bytes(p.read_bytes())
(licenses/'packages.json').write_text(json.dumps(packages,indent=2))
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--windowed','--name','News_idea','--distpath',str(ROOT/'dist'),'--workpath',str(ROOT/'build'/'pyinstaller'),'--specpath',str(stage),'--add-data',str(ROOT/'static')+':static','--add-data',str(licenses)+':licenses','--icon',str(stage/'app.icns'),'--osx-bundle-identifier','local.news-idea.workspace','--target-arch',platform.machine(),str(ROOT/'desktop.py')],check=True,cwd=ROOT)
bundle=ROOT/'dist'/'News_idea.app';p=bundle/'Contents'/'Info.plist';info=plistlib.loads(p.read_bytes());info['CFBundleShortVersionString']='1.0.0';info['CFBundleVersion']='1.0.0';info['NSHumanReadableCopyright']='News_idea local workspace';p.write_bytes(plistlib.dumps(info));subprocess.run(['codesign','--force','--sign','-',str(bundle)],check=True)
print(bundle)
