from pathlib import Path
import sqlite3,json,hashlib
c=sqlite3.connect('ranked_re.db')
paths=[Path('firmware_dump/PRE_FLASH_AUDIT.md'),Path('firmware_dump/boot_acceptance_audit.md'),Path('firmware_dump/boot_acceptance_validation.json'),Path('firmware_dump/recovery_entry_audit.md'),Path('firmware_dump/recovery_entry_validation.json'),Path('firmware_dump/flash_bounds_audit.json'),Path('firmware_dump/boot_safety_audit/metadata_read_result.json'),Path('firmware_dump/boot_safety_audit/stub_page_boundaries.json'),Path('read_boot_metadata.py'),Path('audit_vendor_stub_pages.py')]
for p in paths:
 raw=p.read_bytes();c.execute('INSERT OR IGNORE INTO porting_evidence_artifacts(path,sha256,content) VALUES (?,?,?)',(p.as_posix(),hashlib.sha256(raw).hexdigest(),raw.decode('utf-8-sig')))
p=Path('firmware_dump/boot_safety_audit/metadata_10000600.bin');raw=p.read_bytes()
c.execute('INSERT OR REPLACE INTO firmware_dumps(name,base_address,byte_length,sha256,file_path,verification,content) VALUES (?,?,?,?,?,?,?)',('boot_information_block_10000600',0x10000600,len(raw),hashlib.sha256(raw).hexdigest(),p.as_posix(),'Live bounded word reads; metadata XOR and original application XOR independently match; single capture',raw))
notes=[('boot-live-information-region-extracted','Read512byte boot information block10000600..100007ff using bounded RAM wordread payload/noDATA/COMPLETE/ownflashoperations. This region was outsideprior128KiBcapture. MetadataXOR488a27bc matches; app lengthE908 andXOR25a4f084 matchoriginal2000..10908. RecoverypinconfigFFFFFFFF disabled; defaultrequestmagic. Nativepatches400130e8FFFF0000/ecFFFFFFFF. Cleanup6appcollections/0bootinterfaces; vendorbookkeeping caveat unchanged.'),('boot-actual-config-acceptance-and-recovery-risk','Actualcapturedmetadata selects registerpatch mode andSKIPS bootmetadata/applicationXORgates. Original/basicQMK/VIA reachnative applicationcall8c0 inemulation; bad/erasedresetvectorsalsoattempted. NoautomaticinvalidappUSBfallback guarantee. Configurablephysicalpinrecoverydisabled; retainedmagic5ac396c5 selectsUSBbeforeappread. Requiresworkingexecution/debugpath tosetrequest; independentrecoverynotverified. CurrentQMKresearchreset/bootloaderfunctions haltandneedrealrequestpathbeforeinstall.'),('vendor-stub-boot-page-command-reachability','VendorstubnativeABI boundaryemulation16cases: pages0,15,16,207,208,255 issueerase/programcommands; pages256/FFFFFFFF rejected. NativeRAMguardsfixturevalid, MMIOmodeledbusy0; all128programwordstoresobserved. This provesCPUcommandreachabilitynotphysicalflashpermissions. NativeSTARTmode1 selects2000 appbase, mode0selects0. ControllerE8/ECstartupsettingsnotproofofbootprotection; precisehardwaresemanticsunknown.')]
ids=[]
for topic,note in notes:
 c.execute('INSERT INTO findings(topic,finding) VALUES (?,?)',(topic,note));ids.append(c.execute('select last_insert_rowid()').fetchone()[0])
for p in paths:
 if p.suffix=='.json':c.execute('INSERT INTO diagnostic_experiments(source_file,evidence_json) VALUES (?,?)',(p.as_posix(),p.read_text(encoding='utf-8-sig')))
c.commit();assert c.execute('pragma quick_check').fetchone()[0]=='ok'
print('Saved audit findings',ids,'and512B information block; SQLiteok')
