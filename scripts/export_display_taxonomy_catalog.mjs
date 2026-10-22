import { writeFileSync } from 'node:fs';
import { SUBCATEGORY_RULES } from './display_category_taxonomy.mjs';
import { ROLE_SUBCATEGORY_RULES } from './display_role_subcategory_taxonomy.mjs';

let output = '# 一级、二级、三级专业分类目录（更新版）\n\n说明：三级类别是固定展示分类，不映射或改写具体岗位身份；“其他职业”不是正式二级方向，未纳入本目录。\n';
for (const [level1, directions] of Object.entries(SUBCATEGORY_RULES)) {
  output += `\n## 一级：${level1}\n`;
  for (const direction of directions) {
    if (direction.label === '其他职业') continue;
    output += `\n### 二级：${direction.label}\n`;
    for (const subcategory of ROLE_SUBCATEGORY_RULES[direction.label] || []) output += `\n- 三级：${subcategory.label}\n`;
  }
}
writeFileSync('docs/一级二级三级专业分类目录（更新版）.md', output, 'utf8');
