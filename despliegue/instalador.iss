; Instalador de SIDP para el servidor de la escuela (Inno Setup 6). Lo compila CI:
;   iscc /DVersion=1.0.123 despliegue\instalador.iss      ->  dist\SIDP-Instalador.exe
; Doble clic y "Siguiente": instala SIDP.exe, crea C:\SIDP (Expedientes y sistema), lo pone a arrancar al iniciar
; sesión, abre el puerto 8770 para la página de padres y deja accesos en el escritorio. Desinstalar no borra C:\SIDP.
#ifndef Version
  #define Version "0.0.0"
#endif

[Setup]
AppId={{8C1B0E52-4A0B-4C6E-9B1E-5D1D2E3F4A50}
AppName=SIDP
AppVersion={#Version}
AppVerName=SIDP {#Version}
AppPublisher=Escuela Primaria Delfino Pando
DefaultDirName={autopf}\SIDP
DefaultGroupName=SIDP
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=admin
OutputDir=..\dist
OutputBaseFilename=SIDP-Instalador
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
RestartApplications=no
UninstallDisplayIcon={app}\SIDP.exe
UninstallDisplayName=SIDP

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Dirs]
; El programa se actualiza solo: las cuentas normales pueden cambiar su carpeta.
Name: "{app}"; Permissions: users-modify
Name: "C:\SIDP"; Permissions: users-modify; Flags: uninsneveruninstall
Name: "C:\SIDP\Expedientes"; Permissions: users-modify; Flags: uninsneveruninstall
Name: "C:\SIDP\sistema"; Permissions: users-modify; Flags: uninsneveruninstall

[Files]
Source: "..\dist\SIDP.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\guias\PLAN_DE_EMERGENCIA.md"; DestDir: "{app}"; DestName: "Plan de emergencia.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\SIDP"; Filename: "{app}\SIDP.exe"
Name: "{group}\Expedientes de alumnos"; Filename: "C:\SIDP\Expedientes"
Name: "{group}\Plan de emergencia"; Filename: "{app}\Plan de emergencia.txt"
Name: "{group}\Apagar SIDP"; Filename: "{app}\SIDP.exe"; Parameters: "--apagar"
Name: "{autodesktop}\SIDP"; Filename: "{app}\SIDP.exe"
Name: "{autodesktop}\Expedientes de alumnos"; Filename: "C:\SIDP\Expedientes"
; Trabaja desde que alguien inicia sesión, aunque no se abra la ventana.
Name: "{commonstartup}\SIDP"; Filename: "{app}\SIDP.exe"; Parameters: "--segundo-plano"

[Run]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""SIDP 8770"""; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""SIDP 8770"" dir=in action=allow protocol=TCP localport=8770 profile=any"; Flags: runhidden
Filename: "{app}\SIDP.exe"; Description: "Abrir SIDP"; Flags: postinstall nowait skipifsilent runasoriginaluser
Filename: "{app}\SIDP.exe"; Parameters: "--segundo-plano"; Flags: nowait runasoriginaluser; Check: WizardSilent

[UninstallRun]
Filename: "{app}\SIDP.exe"; Parameters: "--apagar"; Flags: runhidden; RunOnceId: "apagar"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""SIDP 8770"""; Flags: runhidden; RunOnceId: "firewall"
