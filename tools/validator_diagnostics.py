"""Only structured, allow-listed diagnostics can reach public GitHub reports."""
import json,re,pathlib
MESSAGES={
 'missing-resource':'Отсутствует обязательный ресурс модели',
 'unsupported-resource-extension':'Расширение ресурса не поддерживается текущим импортёром',
 'unsupported-token-name':'Не удалось определить язык и модель по Tokens.xml',
 'invalid-locale':'Не поддерживается обозначение языка или модели',
 'incomplete-tokens':'В Tokens.xml нет обязательных ссылок LangDataPath или VoicePath',
 'unsafe-path':'Архив содержит небезопасный путь',
 'missing-model-parameters':'Нет исходных параметров модели; нужен полный совместимый пакет',
 'large-metadata':'Слишком большое описание модели',
 'validator-timeout':'Превышено время проверки импортёром',
 'import-rejected':'Архив отклонён импортёром SmartVoice',
}
FORMATS={'Microsoft Tokens.xml folder','SmartVoice/MultiVoice model package','Vocalizer HDR/DAT','Google backup / metadata ZIP','SmartVoice collection ZIP','Unknown ZIP','Invalid ZIP'}
STAGES={'archive-import','archive-security','archive-extraction','model-metadata','resource-validation','model-parameters','validator-execution'}
def diagnostic(stderr,code,format_hint='Unknown ZIP'):
 try:raw=json.loads(stderr.strip().splitlines()[-1])
 except (ValueError,IndexError):raw={}
 issue=raw.get('code','import-rejected');issue=issue if issue in MESSAGES else 'import-rejected'
 stage=raw.get('stage','validator-execution');stage=stage if stage in STAGES else 'validator-execution'
 klass=raw.get('errorClass','ValidatorProcessError');klass=klass if re.fullmatch(r'[A-Za-z_$][A-Za-z0-9_.$]{0,100}',str(klass)) else 'ValidatorProcessError'
 fmt=raw.get('format',format_hint);fmt=fmt if fmt in FORMATS else 'Unknown ZIP'
 resources=[]
 for value in raw.get('missingResources',[])[:20]:
  leaf=pathlib.PurePosixPath(str(value).replace('\\','/')).name
  if re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',leaf) and (leaf.lower()=='tokens.xml' or not re.search(r'(?i)secret|token|license|password|bearer',leaf)):resources.append(leaf)
 safe={'format':fmt,'stage':stage,'errorClass':klass,'code':issue,'reason':MESSAGES[issue],'missingResources':resources,'exitCode':int(code)}
 safe['stderrExcerpt']=json.dumps(safe,ensure_ascii=False)[:2000]
 return safe
