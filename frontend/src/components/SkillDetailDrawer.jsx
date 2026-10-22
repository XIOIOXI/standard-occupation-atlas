import EvidenceList from './EvidenceList.jsx';
import { matchingSkillEvidence, recruitmentRecordIds } from '../lib/skillEvidence.js';
export default function SkillDetailDrawer({ skill, evidence = [], onClose }) {
  if (!skill) return null;
  const ids = recruitmentRecordIds(skill.evidence_references?.source_recruitment_record_ids);
  const records = matchingSkillEvidence(evidence, skill.evidence_references);
  return <aside className="skill-drawer" aria-label="技能详情" aria-live="polite"><button className="drawer-close" aria-label="关闭详情" onClick={onClose}>×</button>
    <h2>{skill.display_name}</h2><p>基于角色上下文推断的候选技能</p>
    <div className="skill-facts"><span>{skill.skill_type.includes('hard') ? '专业 / 硬技能' : '通用 / 软技能'}</span><span>{skill.scope.includes('occupation_core') ? '岗位核心' : '行业特定'}</span><span>置信度：{skill.confidence.join('、')}</span></div>
    <EvidenceList compact records={records} title="推断参考数据" countLabel={`来自该技能关联 Job Group 的 ${records.length} 条去重招聘记录`} intro="这些招聘记录提供 AI 识别候选技能时的岗位上下文，不代表每条招聘都明确要求此技能。" />
    <details className="technical-provenance"><summary>查看技术来源</summary><dl className="skill-provenance"><dt>来源类型</dt><dd>{skill.source_type}</dd><dt>证据级别</dt><dd>{skill.evidence_levels.join(', ')}</dd><dt>推断版本</dt><dd>{skill.inference_version}</dd><dt>支持 Job Groups</dt><dd>{skill.supporting_group_count}</dd><dt>招聘记录</dt><dd>{ids.join(', ') || '未提供'}</dd></dl></details>
  </aside>;
}
