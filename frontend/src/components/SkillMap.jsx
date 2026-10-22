import { useMemo, useState } from 'react';
import SkillDetailDrawer from './SkillDetailDrawer.jsx';

// Lines in this map only encode display membership: occupation → hard/soft → skill.
// They deliberately do not represent skill dependency, correlation, or PMI.
export default function SkillMap({ skills, evidence }) {
  const [selected, setSelected] = useState(null);
  const groups = useMemo(() => ({ hard: skills.filter(skill => skill.skill_type.includes('hard')), soft: skills.filter(skill => !skill.skill_type.includes('hard')) }), [skills]);
  const slots = (items, side) => items.map((skill, index) => ({ skill, x: side === 'hard' ? 12 : 68, y: 16 + (index / Math.max(items.length - 1, 1)) * 68 }));
  const hard = slots(groups.hard, 'hard'); const soft = slots(groups.soft, 'soft');
  const branchLines = (items, side) => items.map(({ x, y, skill }) => <line key={skill.skill_id} x1={side === 'hard' ? 33 : 67} y1="50" x2={side === 'hard' ? x + 18 : x + 14} y2={y + 8} />);
  return <section className="skill-branch-map" aria-label="技能分支地图">
    <p className="branch-note">分支表示技能的展示分类，不表示技能之间存在依赖、相关性或 PMI 关系。</p>
    <div className="branch-canvas">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><line x1="50" y1="50" x2="33" y2="50" /><line x1="50" y1="50" x2="67" y2="50" />{branchLines(hard, 'hard')}{branchLines(soft, 'soft')}</svg>
      <div className="occupation-anchor">当前职业</div><div className="branch-category hard">专业 / 硬技能</div><div className="branch-category soft">通用 / 软技能</div>
      {[...hard, ...soft].map(({ skill, x, y }) => <button key={skill.skill_id} className="branch-skill" style={{ left: `${x}%`, top: `${y}%` }} onClick={() => setSelected(skill)}><strong>{skill.display_name}</strong><small>{skill.scope.includes('occupation_core') ? '岗位核心' : '行业特定'}</small></button>)}
    </div>
    <SkillDetailDrawer skill={selected} evidence={evidence} onClose={() => setSelected(null)} />
  </section>;
}
