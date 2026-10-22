"""Create immutable SNO v3.1 directory/API catalog from v3 (no mappings)."""
import hashlib,json
from pathlib import Path
from import_sno_v3_directory import parse,assert_unique
ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/'data/taxonomy/sno_v3/SNO职业目录一二三级_v3.md'; D=ROOT/'data/taxonomy/sno_v3_1'
def main():
 if D.exists(): raise FileExistsError(D)
 t=SRC.read_text(encoding='utf8')
 t=t.replace('''二级范围：B2C、电话销售、课程与金融等个人客户销售。\n\n| 三级 ID | 三级类别 | 边界与范围 |\n|---|---|---|\n| L13-02-01 | 远程与电话销售 | 电话在线等远程成交 |\n| L13-02-02 | 现场与顾问销售 | 现场咨询及个人客户顾问成交 |\n\n可明确细分时选择一个三级；二级已明确但细分信息不足或真正综合多个方向时，允许直接落在本二级，不猜三级。''','''二级范围：B2C、课程与金融等个人客户销售；电话、在线、现场等是销售方式标签，不能替代客户类型。仅“电话销售”而无客户类型证据归 L13-09 通用销售。\n\n本二级直达真实岗位，当前不另设三级。\n\n已停用 L13-02-01（远程与电话销售）和 L13-02-02（现场与顾问销售）；二者保留为停用 ID，不可复用或迁移。历史结果必须按标题重新判断客户类型，不能批量迁入 L13-02。''')
 t=t.replace('| L22-02-04 | 综合与通识教学 | 综合课程及通识教学 |','| L22-02-04 | 综合与通识教学 | 标题明确为综合课程、通识课程或跨学科综合教学；仅未说明学科的教师停在 L22-02，不得据此选择本三级 |')
 t=t.replace('二级范围：真实跨职能培养，或正式培养项目未指定最终职业方向。','二级范围：真实培养项目且最终职业方向未明确；不得仅凭“管培/培训/储备”推断跨职能轮岗。已明确行政、人力、开发、销售等职能时归专业目录并加培养标签；仅行业或领域（如银行、绿色金融、农化）不足以确定职能时标 review。')
 nodes=parse(t);assert_unique(nodes); D.mkdir(parents=True); md=D/'SNO职业目录一二三级_v3.1.md';md.write_text(t,encoding='utf8')
 retired={'L13-02-01':{'name':'远程与电话销售','status':'retired','replacement':'sales_method_tag + reclassify customer type from title'},'L13-02-02':{'name':'现场与顾问销售','status':'retired','replacement':'sales_method_tag + reclassify customer type from title'}}
 c={'schema_version':'sno-occupation-catalog-v3.1','taxonomy_version':'sno-v3.1-local-revision','source':{'derived_from':'sno-v3-directory-design','sha256':hashlib.sha256(t.encode()).hexdigest()},'counts':{'level_1':len(nodes),'level_2':sum(len(x['level_2']) for x in nodes),'level_3':sum(len(y['level_3']) for x in nodes for y in x['level_2'])},'retired_category_ids':retired,'classification_contract':{'one_primary_level_2_per_atomic_role':True,'level_3_is_optional':True,'review_target_is_confirmed_common_parent_only':True,'candidate_category_ids_separate_from_target':True},'taxonomy':nodes}
 (D/'sno_occupation_catalog_v3.1.json').write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 (D/'migration_policy_v3.1.json').write_text(json.dumps({'from_version':'sno-v3-directory-design','to_version':c['taxonomy_version'],'retired_ids':retired,'rule':'No bulk migration; reclassify title and preserve legacy placement as review context.'},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print(json.dumps(c['counts'],ensure_ascii=False))
if __name__=='__main__':main()
