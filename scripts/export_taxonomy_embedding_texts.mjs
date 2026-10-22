import { writeFileSync } from 'node:fs';
import { SUBCATEGORY_RULES } from './display_category_taxonomy.mjs';
import { ROLE_SUBCATEGORY_RULES } from './display_role_subcategory_taxonomy.mjs';
const rows=[];
for(const [l1,dirs] of Object.entries(SUBCATEGORY_RULES))for(const d of dirs){if(d.label==='其他职业')continue;for(const r of ROLE_SUBCATEGORY_RULES[d.label]||[])rows.push({category_id:`${l1}/${d.id}/${r.id}`,level_1:l1,level_2:d.label,level_3:r.label,matching_text:`${l1}；${d.label}；${r.label}；代表岗位：${r.label}`});}
writeFileSync('data/processed/record_role_classification_v1/catalog_mappings/taxonomy_embedding_texts_v1.json',JSON.stringify({count:rows.length,rows},null,2)+'\n');
