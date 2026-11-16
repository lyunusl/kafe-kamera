; Kafe Kamera kurulum dosyası (Inno Setup 6).
;
;   kurulum\derle.cmd                       exe'yi derler, Inno Setup kuruluysa kurulum dosyasını da üretir
;   ISCC.exe kurulum\KafeKamera.iss         yalnızca kurulum dosyası: dist\kurulum\KafeKamera-Kurulum-<sürüm>.exe
;
; Adım adım kurar ve AugeLab Studio'yu da kurar; Studio penceresi hiç açılmaz:
;   1. Kafe Kamera     kullanıcı başına (yönetici izni gerekmez) %LOCALAPPDATA%\Programs\KafeKamera altına
;   2. AugeLab Studio  yoksa resmî kurucuyu indirir (SHA-256 doğrulanır), Visual C++ çalışma kitaplığı eksikse Microsoft'tan
;                      indirip imzasını doğrulayarak kurar, Studio'yu sessizce kurar (olmazsa resmî kurulum penceresi)
;   3. AugeLab hesabı  hesap sayfasını tarayıcıda açar (lisans kodu hesapta görünür)
;   4. Lisans kodu     kodu Studio'nun kendi komutuyla arayüzsüz kaydeder (python -m studio verify); kod saklanmaz
; Adım 2-4 atlanabilir: program açılınca başlangıç sayfasındaki sihirbaz aynı adımları gösterir.
; Kaldırınca program silinir; kullanıcı verisi (%LOCALAPPDATA%\KafeKamera: kameralar, videolar, çıktılar) yerinde kalır.

#define Ad "Kafe Kamera"
#define Surum "0.2.0"
#define Kaynak "..\dist\arayuzsuz\KafeKamera.exe"
; studio_kurulum.py ile aynı olmalı (egitim/dene_kurulum.py denetler)
#define StudioUrl "https://studio-desktop-application.s3.eu-central-1.amazonaws.com/AugeLab%20Ai%20Studio.exe"
#define StudioSha256 "cec1e2613620c57fa51c853fc2b6148bc90f978eaf76e351b4b0b0f393681bd8"
#define VcUrl "https://aka.ms/vs/17/release/vc_redist.x64.exe"
#define HesapUrl "https://account.augelab.com/"
#define StudioExe "AugeLab AI Studio.exe"

[Setup]
AppId={{6B0F3E52-2C8A-4C57-9E0B-7A1D4F3C9A21}
AppName={#Ad}
AppVersion={#Surum}
AppVerName={#Ad} {#Surum}
AppPublisher={#Ad}
VersionInfoVersion={#Surum}
VersionInfoProductName={#Ad}
VersionInfoDescription={#Ad} kurulumu
DefaultDirName={autopf}\KafeKamera
DefaultGroupName={#Ad}
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist\kurulum
OutputBaseFilename=KafeKamera-Kurulum-{#Surum}
SetupIconFile=..\packaging\kafekamera.ico
UninstallDisplayIcon={app}\KafeKamera.exe
UninstallDisplayName={#Ad}
Compression=lzma2/fast
SolidCompression=no
WizardStyle=modern
; Açık paneli Windows'un yeniden başlatma yöneticisi kapatamıyor (konsol penceresi): PrepareToInstall kapatır.
CloseApplications=no
RestartApplications=no

[Languages]
Name: "tr"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "masaustu"; Description: "Masaüstüne kısayol oluştur"; GroupDescription: "Kısayollar:"

[Files]
Source: "panel-kapat.ps1"; Flags: dontcopy
Source: "{#Kaynak}"; DestDir: "{app}"; DestName: "KafeKamera.exe"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#Ad}"; Filename: "{app}\KafeKamera.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\{#Ad}"; Filename: "{app}\KafeKamera.exe"; WorkingDir: "{app}"; Tasks: masaustu

[Run]
Filename: "{app}\KafeKamera.exe"; Description: "{#Ad} programını şimdi aç"; Flags: nowait postinstall skipifsilent

[Messages]
tr.FinishedLabel=Kurulum tamamlandı. {#Ad} açıldığında örnek analizi çalıştırabilir ya da kameranızı ekleyebilirsiniz. AugeLab Studio arka planda çalışır; penceresi açılmaz.

[Code]
var
  StudioSayfa: TOutputMsgWizardPage;
  HesapSayfa: TOutputMsgWizardPage;
  LisansSayfa: TInputQueryWizardPage;
  IndirmeSayfa: TDownloadWizardPage;

function StudioKlasoru(): String;
begin
  Result := ExpandConstant('{localappdata}\Programs\AugeLab Studio');
end;

function StudioTamMi(Klasor: String): Boolean;
begin
  Result := FileExists(Klasor + '\{#StudioExe}') and FileExists(Klasor + '\Python\python.exe');
end;

{ Studio'nun yeri: varsayılan klasör, yoksa Windows'un "Yüklü uygulamalar" kaydındaki InstallLocation. }
function StudioYeri(): String;
var
  Koklar: array of Integer;
  Adlar: TArrayOfString;
  I, K: Integer;
  Anahtar, Ad, Yer: String;
begin
  Result := '';
  if StudioTamMi(StudioKlasoru()) then begin
    Result := StudioKlasoru();
    exit;
  end;
  SetArrayLength(Koklar, 2);
  Koklar[0] := HKCU;
  Koklar[1] := HKLM64;
  for K := 0 to 1 do begin
    Anahtar := 'Software\Microsoft\Windows\CurrentVersion\Uninstall';
    if RegGetSubkeyNames(Koklar[K], Anahtar, Adlar) then
      for I := 0 to GetArrayLength(Adlar) - 1 do
        if RegQueryStringValue(Koklar[K], Anahtar + '\' + Adlar[I], 'DisplayName', Ad) and
           (Pos('augelab', Lowercase(Ad)) > 0) and (Pos('studio', Lowercase(Ad)) > 0) and
           RegQueryStringValue(Koklar[K], Anahtar + '\' + Adlar[I], 'InstallLocation', Yer) then begin
          Yer := RemoveQuotes(Yer);
          if (Yer <> '') and StudioTamMi(Yer) then begin
            Result := Yer;
            exit;
          end;
        end;
  end;
end;

function VcKurulu(): Boolean;
var
  Deger: Cardinal;
begin
  Result := (RegQueryDWordValue(HKLM64, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', Deger) and (Deger = 1)) or
            (RegQueryDWordValue(HKLM32, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', Deger) and (Deger = 1));
end;

function MicrosoftImzali(Dosya: String): Boolean;
var
  Kod: Integer;
begin
  Result := Exec('powershell.exe', '-NoProfile -NonInteractive -Command "$s = Get-AuthenticodeSignature -LiteralPath ''' + Dosya +
    '''; if ($s.Status -eq ''Valid'' -and $s.SignerCertificate.Subject -match ''O=Microsoft Corporation'') { exit 0 } else { exit 1 }"',
    '', SW_HIDE, ewWaitUntilTerminated, Kod) and (Kod = 0);
end;

procedure StudioPenceresiniKapat();
var
  Kod, I: Integer;
begin
  { Resmî kurucu bitince Studio'yu kendiliğinden açarsa kapatılır: Kafe Kamera Studio'yu arayüzsüz kullanır. }
  for I := 1 to 8 do begin
    Sleep(1000);
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM "{#StudioExe}" /T', '', SW_HIDE, ewWaitUntilTerminated, Kod);
  end;
end;

function Indir(Url, Ad, Sha256: String): Boolean;
begin
  IndirmeSayfa.Clear;
  IndirmeSayfa.Add(Url, Ad, Sha256);
  IndirmeSayfa.Show;
  try
    try
      IndirmeSayfa.Download;
      Result := True;
    except
      Result := False;
      if not IndirmeSayfa.AbortedByUser then
        MsgBox(Ad + ' indirilemedi: ' + GetExceptionMessage, mbError, MB_OK);
    end;
  finally
    IndirmeSayfa.Hide;
  end;
end;

function StudioKur(): Boolean;
var
  Kurucu, Vc: String;
  Kod: Integer;
begin
  Result := False;
  if not VcKurulu() then begin
    if not Indir('{#VcUrl}', 'vc_redist.x64.exe', '') then exit;
    Vc := ExpandConstant('{tmp}\vc_redist.x64.exe');
    if not MicrosoftImzali(Vc) then begin
      MsgBox('Visual C++ kurulum dosyasının Microsoft imzası doğrulanamadı; çalıştırılmadı.', mbError, MB_OK);
      exit;
    end;
    StudioSayfa.MsgLabel.Caption := 'Visual C++ çalışma kitaplığı kuruluyor. Windows izin sorarsa Evet deyin.';
    if not ShellExec('', Vc, '/install /passive /norestart', '', SW_SHOW, ewWaitUntilTerminated, Kod) or
       not ((Kod = 0) or (Kod = 1638) or (Kod = 3010)) or not VcKurulu() then begin
      MsgBox('Visual C++ çalışma kitaplığı kurulamadı (kod ' + IntToStr(Kod) + ').', mbError, MB_OK);
      exit;
    end;
  end;
  if not Indir('{#StudioUrl}', 'AugeLab-Studio-Kurulum.exe', '{#StudioSha256}') then exit;
  Kurucu := ExpandConstant('{tmp}\AugeLab-Studio-Kurulum.exe');
  StudioSayfa.MsgLabel.Caption := 'AugeLab Studio kuruluyor. Birkaç dakika sürebilir; lütfen bekleyin…';
  WizardForm.NextButton.Enabled := False;
  try
    ShellExec('', Kurucu, '--silent --install-dir "' + StudioKlasoru() + '" --start-menu-shortcut', '', SW_HIDE, ewWaitUntilTerminated, Kod);
    if StudioYeri() = '' then begin
      MsgBox('Sessiz kurulum tamamlanmadı. AugeLab Studio''nun resmî kurulum penceresi açılacak; adımları orada tamamlayın.', mbInformation, MB_OK);
      ShellExec('', Kurucu, '', '', SW_SHOW, ewWaitUntilTerminated, Kod);
    end;
  finally
    WizardForm.NextButton.Enabled := True;
  end;
  Result := StudioYeri() <> '';
  if Result then
    StudioPenceresiniKapat()
  else
    MsgBox('AugeLab Studio kurulamadı. Programı açınca başlangıç sayfasındaki sihirbazla yeniden deneyebilirsiniz.', mbError, MB_OK);
end;

function KodGecerli(Kod: String): Boolean;
var
  I: Integer;
  C: Char;
begin
  Result := (Length(Kod) >= 6) and (Length(Kod) <= 1024);
  for I := 1 to Length(Kod) do begin
    C := Kod[I];
    if not (((C >= 'A') and (C <= 'Z')) or ((C >= 'a') and (C <= 'z')) or ((C >= '0') and (C <= '9')) or
            ((I > 1) and ((C = '.') or (C = '_') or (C = '+') or (C = '/') or (C = '=') or (C = '-')))) then
      Result := False;
  end;
end;

function OrtamYaz(Ad, Deger: String): Boolean;
  external 'SetEnvironmentVariableW@kernel32.dll stdcall';
function OrtamSil(Ad: String; Deger: Cardinal): Boolean;
  external 'SetEnvironmentVariableW@kernel32.dll stdcall';

function LisansKaydet(Kod: String): Boolean;
var
  Yer, Isaret: String;
  Sonuc, Deneme: Integer;
  Calisti: Boolean;
begin
  Result := False;
  Yer := StudioYeri();
  WizardForm.NextButton.Enabled := False;
  LisansSayfa.SubCaptionLabel.Caption := 'Lisans kodu AugeLab Studio''ya kaydediliyor…';
  try
    { Kod yalnızca Studio'nun kendi "verify" komutuna verilir; komut satırında görünmesin diye ortam değişkeniyle
      (studio_kurulum.VERIFY ile aynı). Dosyaya ya da günlüğe yazılmaz. }
    OrtamYaz('KAFE_LISANS_KODU', Kod);
    try
      { Yeni kurulmuş Studio'da ilk deneme başarısız dönebiliyor; bu yüzden komut bir kez daha denenir. }
      for Deneme := 1 to 2 do begin
        Calisti := Exec(Yer + '\Python\python.exe', '-c "import os,runpy,sys; sys.argv=[''studio'',''verify'',' +
          'os.environ.pop(''KAFE_LISANS_KODU'','''')]; runpy.run_module(''studio'',run_name=''__main__'',alter_sys=True)"',
          Yer, SW_HIDE, ewWaitUntilTerminated, Sonuc);
        if Calisti and (Sonuc = 0) then
          Break;
      end;
    finally
      OrtamSil('KAFE_LISANS_KODU', 0);
    end;
    if Calisti and (Sonuc = 0) then begin
      Isaret := ExpandConstant('{localappdata}\KafeKamera');
      ForceDirectories(Isaret);
      SaveStringToFile(Isaret + '\studio-lisans.txt', GetDateTimeString('yyyy-mm-dd hh:nn:ss', '-', ':'), False);
      Result := True;
    end else
      MsgBox('Lisans kodu kaydedilemedi. Kodu AugeLab hesabınızdan yeniden kopyalayıp deneyin ya da internet bağlantınızı kontrol edin.', mbError, MB_OK);
  finally
    WizardForm.NextButton.Enabled := True;
    LisansSayfa.SubCaptionLabel.Caption := 'Kodu yapıştırın. Kod yalnızca AugeLab Studio''ya verilir; Kafe Kamera onu saklamaz.';
  end;
end;

procedure HesapAc(Sender: TObject);
var
  Kod: Integer;
begin
  ShellExecAsOriginalUser('open', '{#HesapUrl}?p=signup', '', '', SW_SHOWNORMAL, ewNoWait, Kod);
end;

procedure KodAl(Sender: TObject);
var
  Kod: Integer;
begin
  ShellExecAsOriginalUser('open', '{#HesapUrl}', '', '', SW_SHOWNORMAL, ewNoWait, Kod);
end;

function Dugme(Sayfa: TWizardPage; Yazi: String; Ust: Integer; Tik: TNotifyEvent): TNewButton;
begin
  Result := TNewButton.Create(Sayfa);
  Result.Parent := Sayfa.Surface;
  Result.Caption := Yazi;
  Result.Top := Ust;
  Result.Left := 0;
  Result.Width := ScaleX(220);
  Result.Height := ScaleY(28);
  Result.OnClick := Tik;
end;

procedure InitializeWizard();
begin
  IndirmeSayfa := CreateDownloadPage('AugeLab Studio', 'Gerekli dosyalar indiriliyor.', nil);
  StudioSayfa := CreateOutputMsgPage(wpInstalling, 'AugeLab Studio',
    'Kafe Kamera kişileri bu bilgisayardaki AugeLab Studio ile algılar.', '');
  HesapSayfa := CreateOutputMsgPage(StudioSayfa.ID, 'AugeLab hesabı',
    'Studio''yu etkinleştiren lisans kodu AugeLab hesabınızda görünür.',
    'AugeLab hesabınız yoksa aşağıdaki düğmeyle tarayıcıda oluşturun ve e-postanıza gelen bağlantıyla onaylayın. ' +
    'Ücretsiz Community planı yeterlidir.'#13#10#13#10'Hesabınız varsa Sonraki''ye basın.');
  Dugme(HesapSayfa, 'AugeLab hesabı oluştur ↗', ScaleY(110), @HesapAc);
  LisansSayfa := CreateInputQueryPage(HesapSayfa.ID, 'Lisans kodu',
    'AugeLab Studio arayüz açılmadan etkinleştirilir.',
    'Kodu yapıştırın. Kod yalnızca AugeLab Studio''ya verilir; Kafe Kamera onu saklamaz.');
  LisansSayfa.Add('Lisans kodu (boş bırakırsanız sonra programdaki sihirbazdan girersiniz):', True);
  Dugme(LisansSayfa, 'Lisans kodumu al ↗', LisansSayfa.Edits[0].Top + LisansSayfa.Edits[0].Height + ScaleY(14), @KodAl);
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = StudioSayfa.ID then begin
    if StudioYeri() <> '' then
      StudioSayfa.MsgLabel.Caption := 'AugeLab Studio bu bilgisayarda kurulu. Sonraki''ye basın.'#13#10#13#10 +
        'Studio arka planda çalışır; Kafe Kamera onun penceresini açmaz.'
    else
      StudioSayfa.MsgLabel.Caption := 'AugeLab Studio bu bilgisayarda kurulu değil. Sonraki''ye basınca:'#13#10#13#10 +
        '• AugeLab''in resmî kurulum dosyası indirilir ve doğrulanır,'#13#10 +
        '• Visual C++ bileşeni eksikse Microsoft''tan kurulur (Windows izin sorabilir),'#13#10 +
        '• AugeLab Studio bu kullanıcı için sessizce kurulur.'#13#10#13#10 +
        'Studio arka planda çalışır; Kafe Kamera onun penceresini açmaz.';
  end;
end;

{ Güncellemede panel açıksa kapatılır (dosyası kullanımda kalmasın). }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Kod: Integer;
begin
  Result := '';
  ExtractTemporaryFile('panel-kapat.ps1');
  if not Exec('powershell.exe', '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
              ExpandConstant('{tmp}\panel-kapat.ps1') + '" -Uygulama "' + ExpandConstant('{app}\KafeKamera.exe') + '"',
              '', SW_HIDE, ewWaitUntilTerminated, Kod) or (Kod <> 0) then
    Result := '{#Ad} kapatılamadı. Programı kapatıp kurulumu yeniden başlatın.';
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  { Studio kurulamadıysa hesap ve lisans adımları programdaki sihirbaza kalır. }
  Result := ((PageID = HesapSayfa.ID) or (PageID = LisansSayfa.ID)) and (StudioYeri() = '');
end;

var
  SonrakiMesgul: Boolean;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Kod: String;
begin
  { Uzun bir adım sürerken düğmeye yeniden basılırsa adım ikinci kez başlamaz. }
  Result := False;
  if SonrakiMesgul then exit;
  SonrakiMesgul := True;
  try
  Result := True;
  if (CurPageID = StudioSayfa.ID) and (StudioYeri() = '') then begin
    if not StudioKur() then
      Result := MsgBox('AugeLab Studio kurulmadan devam edilsin mi? Programı açınca başlangıç sayfasındaki sihirbazla kurabilirsiniz.',
        mbConfirmation, MB_YESNO) = IDYES;
  end else if CurPageID = LisansSayfa.ID then begin
    Kod := Trim(LisansSayfa.Values[0]);
    if Kod = '' then
      Result := MsgBox('Lisans kodu girmeden devam edilsin mi? Programı açınca başlangıç sayfasındaki sihirbazdan girebilirsiniz.',
        mbConfirmation, MB_YESNO) = IDYES
    else if not KodGecerli(Kod) then begin
      MsgBox('Lisans kodu geçersiz görünüyor. AugeLab hesabınızdaki kodu boşluksuz, olduğu gibi yapıştırın.', mbError, MB_OK);
      Result := False;
    end else begin
      Result := LisansKaydet(Kod);
      if Result then LisansSayfa.Values[0] := '';
    end;
  end;
  finally
    SonrakiMesgul := False;
  end;
end;
