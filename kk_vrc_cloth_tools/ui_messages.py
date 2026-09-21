"""English source messages and their Simplified Chinese translations.

Keep identifiers, bone names, configuration keys, and serialized enum values
outside this catalog. Only human-readable text belongs here.
"""

PAIRS = r'''识别依据|Recognition source
源骨角色|Source bone role
待判断|Unassigned
身体骨|Body bone
物理骨|Dynamic bone
忽略|Ignore
仅允许明确的非变形组|Only explicitly non-deforming groups may be ignored
六类归属|Six-class region
接收权重的目标骨|Target weight bone
对应动作骨|Corresponding motion bone
源参考骨（可留空）|Source reference bone (optional)
手指归属|Finger assignment
启用此手指（同指各节保持一致）|Enable this finger (all joints must agree)
动作语义|Motion semantic
目标区域|Target region
区域归属已核对|Region assignment reviewed
允许末端优化调整|Allow terminal refinement
区域名称|Region name
影响区域|Influence region
源动骨链根|Source dynamic chain root
身体跟随模式|Body-follow mode
无法识别 / 待分析|Unrecognized / needs review
需 Agent 逐顶点分析或人工处理|Requires per-vertex agent analysis or manual handling
均匀身体跟随|Uniform body follow
保留原份额，使用语义映射生成初值|Preserve original shares and initialize with semantic mapping
边缘渐变连接|Graded boundary attachment
保留原份额，允许可信原生采样|Preserve original shares and allow trusted native sampling
已核对本区域模式|Region mode reviewed
确认当前行区域；模式或范围改变后失效，执行前复核原权重和角色|Approve this row; changing mode or scope invalidates approval. Source weights and roles are checked again before execution
查看统计|Show statistics
目标分摊骨|Target rotation-sharing bone
旋转比例|Rotation share
动作名称|Pose name
动作|Pose
源动作骨|Source motion bone
目标动作骨|Target motion bone
世界旋转轴|World rotation axis
训练幅度（度）|Training angle (degrees)
用于末端精调|Use for terminal refinement
目标使用独立世界轴|Use a separate target world axis
目标世界旋转轴|Target world rotation axis
额外训练幅度（0 为关闭）|Additional training angle (0 disables)
源骨架识别表|Source rig profile
已有 VRC 表|Existing VRC profile
MMD 通用|Generic MMD
使用维护的 MMD 约定表|Use the maintained MMD convention profile
通用表及已有 R4 Liv 研究证据|Generic profile and existing R4 Liv research
MMD 模型补充表（可选）|MMD model profile (optional)
源动作采样|Source pose sampling
普通 FK/LBS|Standard FK/LBS
不接受源约束|Source constraints are not supported
保留源约束求值|Evaluate source constraints
显式契约；每个姿态必须通过真实 LBS 检查|Explicit contract; every pose must pass actual LBS validation
源参考模式|Source reference mode
适配前源参考|Original unfitted reference
原衣物及完整原权重，必须具有可靠的顶点对应|Original garment with complete source weights and reliable vertex correspondence
当前适配网格参考|Current fitted mesh reference
输入当前适配网格及未传递的源权重；冻结当前源骨架动作基线|Use the fitted mesh with original untransferred weights; freeze the current source motion baseline
优化后碰撞处理|Post-optimization collision policy
保存副本并选点复核|Save a copy and select vertices for review
非碰撞检查通过后保存，用户决定保留或回退|Save after non-collision checks pass; the user decides whether to keep or revert
严格无碰撞|Strict collision-free validation
碰撞检查失败时不写入|Do not write results if collision validation fails
排除 bnip，补给同侧 bust|Exclude bnip and redistribute to same-side bust
动作范围|Motion scope
自动选择|Automatic
根据已识别的身体骨语义选择|Choose from recognized body-bone semantics
上身|Upper body
下身|Lower body
全身|Full body
保留原有手指影响|Preserve original finger influence
仅保留原衣物已有的手指份额；不会采样加入新的手指影响|Preserve only existing finger shares; do not sample new finger influence
接着执行已指定范围的末端精调|Continue with terminal refinement in the specified region
原衣物（完整权重）|Original garment (complete weights)
已适配衣物|Fitted garment
目标素体|Target body
动作预设|Pose preset
抬臂、屈肘与躯干|Arm raise, elbow bend, and torso
髋膝及躯干|Hip, knee, and torso
上下身动作|Upper- and lower-body poses
手腕末端|Wrist refinement
双侧扭转、弯曲、侧偏|Twist, bend, and side tilt on both sides
高级动作设置|Advanced pose settings
身体采样可信度|Body sampling confidence
初值来源|Initialization source
Blender 最近面插值|Blender nearest face interpolated
仅用原生 POLYINTERP_NEAREST|Use native POLYINTERP_NEAREST only
已有目标分布|Existing target distribution
按对应顶点读取已审核目标衣物的身体权重|Read reviewed target body weights using corresponding vertices
仅语义映射|Semantic mapping only
不用空间传递|No spatial transfer
本轮结果目录|Run output directory
外部 Python|External Python
依赖目录（可选）|Dependencies directory (optional)
配置文件|Configuration file
启用穿模约束迭代|Enable collision-constraint iterations
末端过渡环数|Terminal transition rings
末端小角度（度）|Terminal small angle (degrees)
六类初值副本|Six-class initialization copy
主体优化副本|Main optimization copy
末端优化副本|Terminal optimization copy
运行与配置文件|Runtime and configuration files
编辑动作预设|Edit pose preset
高级求解参数|Advanced solver settings
展开身体骨与候选骨|Show body and candidate bones
选中源骨的映射与高级设置|Selected source bone: mapping and advanced settings
选中目标骨的高级设置|Selected target bone: advanced settings
待分析|Needs review
均匀|Uniform
渐变|Gradient
末端|Terminal
主体|Main
衣物权重工作流|Garment weight workflow
求解衣物权重|Solve garment weights
1 · 输入与扫描|1 · Inputs and scan
源输入须保留完整原权重，与适配网格一致；准备时冻结副本。|Source must retain complete original weights and match the fitted mesh; preparation freezes a copy.
扫描骨骼与动骨根区域|Scan bones and dynamic root regions
2 · 审核身体与物理骨区域|2 · Review body and dynamic regions
源骨：指定角色与身体区域|Source bones: assign roles and body regions
识别依据：MMD 维护表；未知及物理候选仍需审核|Recognition: maintained MMD profile; unknown and dynamic candidates still require review
角色编辑后刷新动骨区域|Refresh dynamic regions after editing roles
目标骨：仅列出素体实际有权重的骨骼|Target bones: only bones with actual body weights
补充根骨区域|Add missing root regions
重新粗识别|Reclassify regions
此根链确认为动骨|Mark this root chain as dynamic
查看网格范围|Show mesh region
统计建议：|Suggested mode: 
均匀跟随|Uniform follow
边缘渐变|Boundary gradient
需逐顶点分析或人工处理后再确认|Analyze per vertex or handle manually before approval
统计与高级区域设置|Statistics and advanced region settings
记录当前选区|Capture current selection
恢复根链范围|Restore root-chain scope
添加区域|Add region
删除区域|Remove region
手动添加区域|Add region manually
检查区域与映射|Check regions and mappings
3 · 六类迁移与主体优化|3 · Six-class transfer and main optimization
预览六类初值|Preview six-class initialization
写入初值副本|Write initialization copy
生成预设动作（补充缺项）|Generate preset poses (add missing entries)
姿态对照：先选预设，再核对幅度|Pose comparison: select a preset, then review angles
添加动作|Add pose
删除动作|Remove pose
预览动作|Preview pose
恢复姿态|Restore pose
多骨分摊（留空则仅使用上方目标骨）|Rotation sharing (leave empty to use only the target bone above)
添加分摊骨|Add sharing bone
删除末项|Remove last entry
求解主体权重|Solve main weights
独立验收|Independent validation
写入主体副本|Write main copy
4 · T pose 末端局部精调|4 · Local terminal refinement in T pose
只使用上方勾选为末端的动作与目标候选骨|Use only terminal poses and the selected target candidate bones
记录末端顶点选区|Capture terminal vertex selection
尚未指定末端范围|No terminal region specified
求解末端权重|Solve terminal weights
写入末端副本|Write terminal copy
检查求解依赖|Check solver dependencies
导入配置|Import configuration
导出配置|Export configuration
清空配置（不删除结果）|Clear configuration (keep results)
显示当前结果|Show current result
选择碰撞顶点|Select collision vertices
回退上一版本|Revert to previous version
保存结果副本|Save result copy
侧别|Side
左|Left
右|Right
未指定|Unassigned
鞋带动骨|Lace dynamic bone
参与采样|Include in sampling
已逐顶点分析|Analyzed per vertex
需填写结论；不是自动支持未知模式|Enter the analysis conclusion; unknown modes are not supported automatically
分析结论|Analysis conclusion
已核对区域与份额|Region and shares reviewed
脚踝动作骨|Ankle motion bone
前掌动作骨|Forefoot motion bone
前掌方向（世界）|Forward direction (world)
上方向（世界）|Up direction (world)
原鞋（完整原权重）|Original shoes (complete source weights)
适配后的鞋|Fitted shoes
手动设置脚部骨骼与方向|Manually set foot bones and directions
编辑姿态预设|Edit pose preset
高级采样与优化参数|Advanced sampling and optimization
配置文件与命名|Configuration files and naming
使用目标脚空间分布，保留原身体/动骨份额|Use target foot distribution and preserve source body/dynamic shares
长鞋头延伸|Extend long toe caps
连续性修复强度|Continuity smoothing strength
候选拓扑扩展环数|Candidate topology expansion rings
最低可信采样量|Minimum trusted sample mass
一键运行时加入间距优化 B|Include gap optimization B in one-click runs
低权重随机辅助|Low-weight random auxiliary poses
随机姿态数量|Random pose count
辅助姿态权重|Auxiliary pose weight
随机种子|Random seed
保留 A 的约束强度|Regularization toward A
结果目录|Output directory
副本名称前缀|Copy name prefix
鞋子工作流|Shoe weight workflow
鞋子配置文件|Shoe configuration file
复杂平底鞋权重迁移|Complex Flat-Shoe Weight Transfer
扫描骨骼与鞋带根区域|Scan bones and lace root regions
2 · 审核身体与鞋带区域|2 · Review body and lace regions
源骨：未知项需手动指定角色和侧别|Source bones: manually assign roles and sides for unknown entries
目标候选：仅列出素体有正权重的骨骼|Target candidates: only bones with positive body weights
3 · 方向、延伸与连续性|3 · Directions, extension, and continuity
左脚|Left foot
右脚|Right foot
由动作骨关节位置推断前掌方向|Infer foot directions from motion joints
4 · 平底鞋姿态预设与优化|4 · Flat-shoe pose presets and optimization
标准训练 7 个 × 1.0；独立验证 4 个|7 standard training poses × 1.0; 4 held-out validation poses
随机：踝 ±15°，前掌 −8～12°，侧倾 ±6°|Random: ankle ±15°, forefoot -8 to 12°, tilt ±6°
5 · 执行与结果|5 · Run and results
检查配置|Check configuration
生成 A：采样与连续性|Build A: sampling and continuity
从 A 优化 B|Optimize B from A
一键执行（保留原鞋）|Run all (preserve original shoes)
原鞋|Original shoes
打开本轮报告目录|Open run report directory
导入配置（可选）|Import configuration (optional)
仅处理平底鞋；模型结果请保存 blend|Flat shoes only; save the blend file to retain model results
手动编辑|Manual Editing
动骨衣物权重迁移|Dynamic Garment Weight Transfer
导出前动骨清理|Pre-export Dynamic Bone Cleanup
清理此根链|Remove this root chain
待导出骨架|Export armature
已核对勾选链没有外部物理或导出引用|Selected chains have no external physics or export references
扫描所选根链|Scan selected root chains
重新扫描|Rescan
清理勾选根链|Remove checked root chains
选择导出骨架＋网格结构，也可直接选择网格|Select the export armature and meshes, or select a bound mesh
KK 名单身体骨始终保留；非身体骨只整链删除|Always preserve listed KK body bones; remove non-body bones only as complete chains
自动扫描导出结构|Scan export structure automatically
重新扫描权重与依赖|Rescan weights and dependencies
清理勾选根链（自动备份）|Remove checked chains (automatic backup)
新手保守权重工作流|Beginner conservative weight workflow
衣物权重 · 新手保守预设|Garment Weights · Beginner Preset
最近面插值 · 六类守恒 · 穿模检查 · 独立副本|Nearest face interpolation · six-class conservation · collision checks · separate copies
① 应用保守预设并自动扫描|1. Apply conservative preset and scan
② 核对区域模式及动骨身份|2. Review region modes and dynamic bone roles
③ 自动计算 → 验收 → 生成副本|3. Solve → validate → create copies
动作可在下方详细流程预览与恢复|Preview and restore poses in the detailed workflow below
末端仅使用详细流程已指定的局部选区和候选|Terminal refinement uses only the specified local selection and candidates
高亮区域|Highlight region
高亮后请按 Tab 返回物体模式再计算|After highlighting, press Tab to return to Object Mode before solving
Python 与依赖设置|Python and dependency settings
检查依赖|Check dependencies
运行中按 Esc 取消；结果自动保存为独立 blend|Press Esc to cancel; results are saved as a separate blend file
归属|Ownership
源饰品|Source accessory
识别 MMD 标准身体挂点|Recognize standard MMD body attachment bones
自有链根|Owned chain roots
外部挂点骨|External attachment bones
已确认属于本饰品的完整骨链；非标准骨不自动判为动骨|Complete chains confirmed as belonging to this accessory; unknown bones are not automatically dynamic
身体骨或其他资产的依附骨；精确骨名，逗号分隔|Body or other-asset attachment bones; comma-separated exact names
备份/结果目录|Backup/output directory
饰品骨架预处理|Accessory rig preprocessing
使用活动网格|Use active mesh
选中骨加入自有链根|Add selected bones as owned roots
选中骨加入外部挂点|Add selected bones as external attachments
扫描计划|Scan plan
备份并生成独立饰品|Back up and create independent accessory
查看报告|View report
饰品独立骨架清理|Accessory Independent Rig Cleanup
将源骨架选中骨加入上项|Add selected source bones to the field above
根接收外部份额；自有动骨权重不变。|Roots receive external shares; owned dynamic weights remain unchanged.
多挂点分别保留；不强制合成单根。|Keep multiple attachment points separate; do not force a single root.
1. 扫描计划|1. Scan plan
2. 备份并生成独立饰品|2. Back up and create independent accessory
每件饰品生成独立网格和独立骨架。|Create a separate mesh and armature for each accessory.
源衣物|Source garment
额外保留骨|Additional protected bones
精确骨名，以逗号分隔；也可选骨后点加入|Exact bone names, separated by commas; or add selected bones
完整保留链根|Roots of chains to preserve
会保留整条分支；其他衣物支链请明确排除|Preserves entire branches; explicitly exclude branches belonging to other garments
确认清理分支根|Confirmed branch roots to remove
已确认无用的完整分支；不会覆盖身体骨保护、显式保留、正权重和必要依赖；冲突会停止|Confirmed unused branches; body protection, explicit pins, positive weights, and dependencies take precedence; conflicts stop execution
确认可清理骨|Confirmed bones to remove
审核后输入精确骨名；仅这些节点，不含后代。不能覆盖身体骨保护或必要依赖|Enter reviewed exact names; applies to these nodes only, not descendants. Cannot override body protection or required dependencies
保留承重骨的直接末端候选|Preserve immediate tip candidates of weighted bones
自动摆 T pose（源骨架局部 X）|Auto T pose (source armature local X)
已检查 T pose，确认落实静止姿态并清理|T pose reviewed; apply as rest pose and clean up
左上臂|Left upper arm
右上臂|Right upper arm
左前臂|Left forearm
右前臂|Right forearm
左手腕|Left wrist
右手腕|Right wrist
MMD 衣物预处理|MMD Garment Preprocessing
扫描、独立副本 T pose、依赖保留清理与验证|Scan, T-pose an independent copy, clean up with dependency protection, and validate
选中骨加入保留|Protect selected bones
选中骨作为完整链根|Preserve chains rooted at selected bones
选中骨作为确认清理分支根|Confirm selected branch roots for removal
选中骨已确认可清理|Confirm selected bones for removal
扫描清理预览|Scan cleanup preview
创建姿态候选|Create pose candidate
调整候选姿态|Adjust candidate pose
落实 T pose 并清理|Apply T pose and clean up
再次保存结果副本|Save result copy again
1. 扫描清理预览|1. Scan cleanup preview
2. 备份并创建姿态候选|2. Back up and create pose candidate
调整候选骨架姿态|Adjust candidate armature pose
3. 落实 T pose、清理并验证|3. Apply T pose, clean up, and validate
定位候选/结果|Show candidate/result
仍需约束采样适配，未达优化器入口|Constraint sampling adaptation is still required before optimization
普通 LBS 骨架入口检查通过|Standard LBS rig checks passed
保留原件；第一版不处理形态键/SDEF。|Preserves originals; this version does not process shape keys or SDEF.
保留规则与清理预览|Preservation Rules and Cleanup Preview
标准身体骨无条件保留（含零权重骨）|Always preserve standard body bones, including zero-weight bones
用途不明的骨默认保留；审核后才能清理。|Keep bones with unknown purpose until reviewed.
完整链可含其他衣物支链，请核对归属。|Complete chains may include other garments; check ownership.
在文本编辑器查看完整报告|View full report in the Text Editor
T pose 骨骼映射|T-Pose Bone Mapping
无法识别时可填写，或关闭自动摆姿态。|Fill in unrecognized mappings, or disable automatic posing.
同时清理末端骨对应权重和顶点组|Also remove weights and vertex groups for deleted tip bones
仅清理本次实际删除的末端骨同名组；有权重末端仍需先启用合并到父骨，跳过的骨骼不受影响|Only remove groups for tips actually deleted; weighted tips require merging to parent first. Skipped bones are unaffected
均值 |Mean 
  方差 |  Variance 
极差 |Range 
  相对极差 |  Relative range 
核心顶点：|Core vertices: 
范围：显式选区 |Scope: explicit selection, 
范围：根链实际非零权重顶点|Scope: vertices with nonzero root-chain weights
已配置 |Configured: 
 个动作| poses
随机实际权重 |Effective random weight: 
/个；总量上限 1.4| per pose; total capped at 1.4
间距 RMS：A |Gap RMS: A 
 个顶点| vertices
 骨）| bones)
高亮 |Highlight 
粗识别：均匀 |Classification: uniform 
、渐变 |, gradient 
、无法识别 |, unrecognized 
待审核 |Pending review 
 躯干扭转| Torso twist
躯干扭转|Torso twist
躯干前屈|Torso bend
躯干侧弯|Torso side bend
 抬臂| Arm raise
 前后摆臂| Arm swing
 屈肘| Elbow bend
 抬腿| Leg raise
 腿外展| Leg abduction
 屈膝| Knee bend
 手腕扭转| Wrist twist
 手腕弯曲| Wrist bend
 手腕侧偏| Wrist tilt
纯动骨|Dynamic only
无法识别：需 Agent 分析或人工处理|Unrecognized: agent analysis or manual handling required
应用已有保守参数；无法识别或未验收区域会停止，结果仅写入副本|Apply existing conservative settings; unrecognized or unreviewed regions stop execution; write results to copies only
确认此骨链为保留动骨|Confirm this chain as retained dynamic bones
确认本区域模式|Confirm region mode
已确认可清理，且无保留依赖|Confirmed removable with no required dependencies
'''

PAIRS += r''' 个区域顶点；有效源变形贡献将全部保留。| region vertices; all effective source deformation contributions are preserved.
 个已验收项。请逐区验收。| approved entries. Review each region.
 个待审核鞋带区域| lace regions awaiting review
 个根骨候选区域；请确认动骨身份及身体跟随模式。| candidate root regions; confirm dynamic roles and body-follow modes.
 个源组，| source groups, 
 个源顶点；可修正选区后重新记录。| source vertices; adjust the selection and capture again if needed.
 个碰撞相关顶点；报告保留既有、新增及恶化情况。| collision-related vertices; the report distinguishes existing, new, and worsened collisions.
 个约束。| constraints.
 个绑定网格（含隐藏网格），| bound meshes (including hidden meshes), 
 个训练 / | training / 
 个顶点；计算前请退出编辑模式。| vertices; exit Edit Mode before solving.
 个验证姿态| validation poses
 条根链可清理。| root chains eligible for removal.
 条预设动作；已有动作保留。| preset poses; existing poses preserved.
 根骨骼；骨架数据备份：| bones; armature data backup: 
 独立姿态 RMS | held-out pose RMS 
 顶点。可写入独立初值副本。| vertices. Ready to write an initialization copy.
 顶点；回退 | vertices; fallback 
 骨 → 保留 | bones → preserve 
 骨；保留 | bones; preserve 
 骨；固定挂点 | bones; fixed attachments 
: 保留动骨尚未接入目标骨架|: retained dynamic bones are not attached to the target rig
: 尚未逐区验收，或原权重/角色/范围已变化，请重新验收|: not reviewed, or source weights/roles/scope changed; review again
: 未启用的手指请映射到同侧非手指身体骨|: map disabled fingers to same-side non-finger body bones
: 权重目标不在素体白名单/同侧区域|: weight target is outside the body whitelist or same-side region
: 源骨链根不存在|: source chain root does not exist
: 目标分摊骨需唯一，正比例之和必须为 1|: sharing bones must be unique and positive shares must sum to 1
: 缺少有效目标动作骨|: missing valid target motion bone
: 需要一个有效骨架修改器|: requires exactly one valid Armature modifier
: 顶点选区已过期，请重新捕获|: vertex selection is stale; capture again
A 已生成；可继续优化 B|A generated; ready to optimize B
B 通过数值验收|B passed numerical validation
MMD 识别表已改变，请保存配置后重新扫描审核|MMD profile changed; save the configuration, then rescan and review
三个输入必须是不同对象|The three inputs must be different objects
上一版本不存在|Previous version does not exist
不支持的工作流配置格式|Unsupported workflow configuration format
仍有未确认的源骨角色，请在骨骼列表中处理|Some source roles are unconfirmed; review the bone list
优化任务运行中，请等待完成或取消|Optimization is running; wait for completion or cancel
优化运行中；Esc 可取消。完成后请执行独立验收。|Optimization running; Esc cancels. Run independent validation afterward.
依赖不完整，需要 numpy/scipy/osqp：|Missing dependencies; NumPy/SciPy/OSQP required: 
保守预设的参数已改变，请重新套用，或使用详细流程运行自定义参数|Conservative settings changed; reapply the preset or use the detailed workflow for custom settings
保留 A；B 未启用或未通过验收，见报告|Keeping A; B was disabled or failed validation. See the report
先扫描区域|Scan regions first
先扫描当前输入|Scan the current inputs first
先指定源衣物|Set the source garment first
先指定源饰品|Set the source accessory first
先指定该根区域的左右侧|Assign a side to this root region first
先检查并确认姿态候选|Inspect and approve the pose candidate first
先添加区域并选择骨链根|Add a region and choose its chain root first
先生成 A|Generate A first
先生成姿态候选|Create a pose candidate first
先生成或添加动作|Generate or add poses first
先选择区域|Select a region first
六类初值已写入独立副本；源权重与原适配衣物保留。|Six-class initialization written to a copy; source weights and the fitted original are preserved.
六类预览完成：|Six-class preview complete: 
关节无法推断方向，请手动设置|Cannot infer direction from joints; set it manually
冻结源参考不存在或已改变，请重新准备本轮|Frozen source reference is missing or changed; prepare the run again
冻结源骨架的结构或约束已改变，请重新准备|Frozen source rig structure or constraints changed; prepare again
动作对应骨不存在|Mapped motion bone does not exist
动作语义重复: |Duplicate motion semantic: 
动作预览中：请检查两套骨架的动作方向，再点击恢复姿态。|Pose preview: check motion directions on both rigs, then restore the pose.
动作骨或旋转轴无效|Invalid motion bone or rotation axis
动骨根区域重叠|Dynamic root regions overlap
包含已知身体骨，禁止自动清理|Contains known body bones; automatic removal is prohibited
区域已刷新，请逐项审核|Regions refreshed; review each entry
区域根骨无效|Invalid region root bone
区域选区过期|Region selection is stale
原生传递需要目标衣物/素体处于共同静止姿态；请先恢复 T pose|Native transfer requires the target garment and body in a shared rest pose; restore T pose first
原衣物与目标衣物的顶点拓扑不对应|Source and target garment vertex topology does not match
原衣物须用独立源骨架；目标素体和适配衣物须用同一目标骨架|Source garment requires a separate rig; target body and fitted garment must share the target rig
原鞋和适配鞋拓扑不对应|Original and fitted shoe topology does not match
同一手指的各指节启用状态必须一致|All joints of a finger must share the same enabled state
在候选骨架调整姿态；完成后返回 Object 模式并确认。|Adjust the candidate rig pose; return to Object Mode and confirm when finished.
在源骨架 Pose 模式选择骨骼|Select source rig bones in Pose Mode
在源骨架 Pose 模式选择骨骼后添加|Select source rig bones in Pose Mode, then add them
外部 Python 与 numpy/scipy/osqp 可用。|External Python and NumPy/SciPy/OSQP are available.
姿态控制骨不存在|Pose control bone does not exist
存在指向骨架的驱动引用|A driver references this armature
存在未指定骨骼的骨架约束引用|A constraint references the armature without specifying a bone
存在骨骼父级对象|An object is parented to this bone
审核未通过：|Review failed: 
小腿参考长度不足，请手动设置|Lower-leg reference is too short; set directions manually
尚无候选或结果|No candidate or result yet
尚无结果报告|No result report yet
左右肢体与躯干方向退化，不能生成动作轴|Limb and torso directions are degenerate; cannot generate motion axes
已保存 |Saved 
已保存结果副本：|Saved result copy: 
已取消求解，未写入权重。|Solve canceled; no weights written.
已回退显示上一版本，优化副本保留隐藏。|Showing the previous version; the optimization copy remains hidden.
已备份并生成独立候选；可在候选骨架 Pose 模式微调。|Backed up and created an independent candidate; refine its rig in Pose Mode.
已套用保守预设并备份旧配置；请逐区确认模式和骨骼角色。|Conservative preset applied and old configuration backed up; review region modes and bone roles.
已将该根骨链标为动骨，请核对模式|Root chain marked as dynamic; review its mode
已将该链实际加权骨标为保留动骨；仍需确认区域模式。|Weighted bones in this chain marked as retained dynamic bones; region mode still needs approval.
已恢复预览前姿态。|Restored the pose from before preview.
已指定源衣物；下一步扫描。|Source garment set; scan next.
已按本例验收配置核对，保留每顶点原始混合份额|Checked against the accepted configuration; preserve original per-vertex mixed shares
已撤销本区域审核；重新确认前不会执行迁移。|Region approval revoked; transfer requires renewed approval.
已有优化任务运行中|An optimization task is already running
已有配置：请先导出或使用清空配置按钮，避免覆盖人工判断|Configuration already exists; export or clear it first to preserve manual decisions
已清理 |Removed 
已生成独立饰品；挂点待接入目标，原件保留。|Independent accessory created; attachment points still need target binding. Original preserved.
已由目标骨架推断脚部方向|Foot directions inferred from the target rig
已补充 |Added 
已记录 |Captured 
已选中 |Selected 
归属已更新，退出 Pose 模式后扫描。|Ownership updated; leave Pose Mode and scan.
当前场景已切换，停止自动写入；可回原场景手动验收|Scene changed; automatic writing stopped. Return to the original scene for manual validation
当前适配参考模式要求源参考本身就是同一适配网格，并保留未迁移原权重；不能以旧网格冒充|Fitted-reference mode requires the matching fitted source mesh with original untransferred weights; the old unfitted mesh is not valid
当前鞋类流程要求每侧有身体参考顶点|The shoe workflow requires body reference vertices on each side
待分析区域需逐顶点分析后填写结论：|Analyze this region per vertex and enter a conclusion: 
手腕与肘位置重合，无法确定扭转轴|Wrist and elbow positions coincide; cannot determine twist axis
扫描完成：|Scan complete: 
扫描完成：生成 |Scan complete: generated 
找不到外部 Python，请在运行设置中配置|External Python not found; configure it in runtime settings
旋转轴无效|Invalid rotation axis
无权重且未发现 Blender 依赖|No weights or detected Blender dependencies
无法识别的区域不能直接运行自动算法；需 Agent 逐顶点分析或人工处理，再明确适用模式|Unrecognized regions cannot run automatically; use per-vertex agent analysis or manual handling to determine a supported mode
有动骨未包含在审核区域中|Some dynamic bones are outside reviewed regions
有效源变形骨不能忽略: |Effective source deform bones cannot be ignored: 
未保存的文件请先选择结果目录，然后再次应用预设|For unsaved files, choose an output directory, then reapply the preset
未识别小腿参考骨，请手动设置方向|Lower-leg reference bone not recognized; set directions manually
未识别脚部动作骨，请手动设置|Foot motion bones not recognized; set them manually
未选中顶点|No vertices selected
未选择骨骼|No bones selected
末端精调需要已指定且有效的局部顶点范围；可先取消末端精调完成主体|Terminal refinement requires a valid local vertex region; disable it to run main optimization first
末端精调需要已指定的素体加权骨候选|Terminal refinement requires selected candidates with actual body weights
末端顶点选区无效|Invalid terminal vertex selection
本轮已有初值副本|This run already has an initialization copy
本阶段设置已改变，请重新求解，不能写入旧候选|Stage settings changed; solve again before writing a candidate
权重或依赖已变化，请重新扫描|Weights or dependencies changed; rescan
权重检查通过，可保存并选点排查碰撞。|Weight checks passed; save and inspect collision vertices.
根区域与骨骼角色不一致：|Root region conflicts with bone roles: 
根骨不存在：|Root bone does not exist: 
检查了 |Checked 
检查通过：|Checks passed: 
求解任务正在运行|A solve is running
求解依赖不可用，请在运行设置中配置 Python 与 NumPy/SciPy/OSQP：|Solver dependencies unavailable; configure Python and NumPy/SciPy/OSQP in runtime settings: 
求解失败，未写入。请查看 |Solve failed; nothing written. See 
求解完成；尚未写入，请执行独立验收。|Solve complete; not yet written. Run independent validation.
没有优化结果副本|No optimization result copy
没有勾选可清理的根链|No eligible root chains checked for removal
没有选中的骨骼|No bones selected
源对象变化，请重新指定归属并扫描。|Source object changed; assign ownership and scan again.
源对象已变化，请重新扫描|Source object changed; rescan
源衣物已变化；已清空旧规则，请重新扫描。|Source garment changed; old rules cleared. Rescan.
源鞋或输入已变更，请重新扫描|Source shoes or inputs changed; rescan
源骨仍有待判断的角色或侧别|Some source bone roles or sides remain unassigned
源骨列表已过期|Source bone list is stale
源骨归属已变更，请刷新动骨区域|Source ownership changed; refresh dynamic regions
目标候选必须在当前素体实际有正权重|Target candidates must have positive weights on the current body
目标状态已变化，请重新预览|Target state changed; preview again
目标素体骨骼的六类归属仍有待确认项|Some target body six-class assignments remain unconfirmed
绑定网格启用了骨骼封套|A bound mesh uses bone envelopes
编辑就绪：|Ready for editing: 
缺少同侧实际加权 bust 补偿骨|Missing same-side weighted bust compensation bone
缺少手腕轴对应骨|Missing bone for the wrist axis
缺少映射，未生成: |Missing mapping; not generated: 
自动流程已停止：|Automatic workflow stopped: 
自有/依赖 |Owned/dependent 
被约束引用|Referenced by a constraint
规则已变更，退出 Pose 模式后重新扫描。|Rules changed; leave Pose Mode and rescan.
规则或映射已变化，请重新扫描|Rules or mappings changed; rescan
规则或源对象已变化，请重新扫描|Rules or source object changed; rescan
该子树包含已识别身体骨，不能整链标为动骨: |Subtree contains recognized body bones and cannot be marked entirely dynamic: 
该结果尚未生成|This result has not been generated
请先写入主体结果|Write the main result first
请先写入六类初值副本|Write the six-class initialization copy first
请先切换到物体模式|Switch to Object Mode first
请先应用保守预设并完成必要检查|Apply the conservative preset and complete required checks first
请先扫描导出结构|Scan the export structure first
请先添加影响区域|Add an influence region first
请先退出 Pose/Edit 模式|Leave Pose/Edit Mode first
请先选择原衣物、适配衣物和目标素体|Select the original garment, fitted garment, and target body first
请先选择源衣物网格|Select the source garment mesh first
请在原衣物或对应衣物副本上选择顶点|Select vertices on the source garment or its corresponding copy
请在独立、可编辑的导出骨架副本上清理|Clean up an independent, editable export armature copy
请在目标骨列表中勾选允许末端调整的身体骨|Enable terminal adjustment for body bones in the target list
请指定配置文件路径|Specify a configuration file path
请核对动作方向和幅度。|Check pose directions and angles.
请确认采用目标脚空间分布策略|Confirm use of the target foot spatial distribution
请记录有效末端顶点选区|Capture a valid terminal vertex selection
请设置本轮结果目录|Set the run output directory
请退出编辑模式后扫描|Leave Edit Mode before scanning
请退出输入网格的编辑/权重绘制模式后计算|Leave Edit/Weight Paint Mode on input meshes before solving
请选择一个导出骨架及其网格结构，或绑定该骨架的网格；不能同时处理多个骨架|Select one export armature and its meshes, or a bound mesh; multiple armatures cannot be processed together
请选择原鞋、适配鞋、目标素体|Select the original shoes, fitted shoes, and target body
请选择对象并扫描|Select objects and scan
请选择有效源骨链根|Select a valid source chain root
请选择源网格|Select a source mesh
请选择结果保存目录|Choose an output directory
请选择脚踝与前掌动作骨|Select ankle and forefoot motion bones
请选择骨架|Select an armature
请逐个审核鞋带根骨区域：|Review each lace root region: 
请配置本阶段的源/目标动作骨与世界轴|Configure source/target motion bones and world axes for this stage
请重新扫描当前输入和配置|Rescan current inputs and settings
身体映射仍指向已排除的 bnip，请改为同侧 bust|Body mapping still targets excluded bnip bones; use same-side bust bones
适配鞋与素体须共用目标骨架；原鞋使用独立源骨架|Fitted shoes and body must share the target rig; original shoes require a separate source rig
选区拓扑已过期|Selection topology is stale
选区拓扑已过期，请重新捕获|Selection topology is stale; capture again
选区网格与原衣物拓扑不一致|Selected mesh topology does not match the original garment
选择三件输入对象，然后扫描骨骼。|Select the three input objects, then scan bones.
选择单件衣物；原对象保留，处理独立副本。|Select one garment; preserve the original and process a separate copy.
选择导出骨架及网格结构，或绑定该骨架的网格，然后扫描。|Select the export armature and meshes, or a bound mesh, then scan.
选择源动骨链根或记录顶点选区|Choose a source dynamic root or capture a vertex selection
配置已变化或未预览，请重新准备六类计划|Configuration changed or was not previewed; prepare the six-class plan again
配置已导入，请检查对象对应关系并重新预览。|Configuration imported; check object assignments and preview again.
配置已导出|Configuration exported
配置已导出。|Configuration exported.
配置已清空，衣物结果未删除。|Configuration cleared; garment results preserved.
配置已载入，请审核动骨区域和空间策略|Configuration loaded; review dynamic regions and spatial policy
配置通过：|Configuration passed: 
链内仍有实际权重（保留整链及末端）|Chain has actual weights (preserve the entire chain and tips)
非碰撞检查失败或严格策略未通过，禁止写入。|Non-collision checks or strict policy failed; writing is blocked.
非碰撞检查或严格碰撞验收未通过|Non-collision checks or strict collision validation failed
非碰撞检查或严格策略未通过，保留报告，不写入优化副本|Non-collision checks or strict policy failed; report retained, optimization copy not written
预设动作映射不完整，请核对源与目标动作骨|Preset pose mapping is incomplete; check source and target motion bones
预设无法确定解剖轴：请补齐躯干及左右肢体的动作语义/对应骨，或使用高级手动动作|Cannot infer anatomical axes; complete torso and bilateral limb semantics/mappings, or configure poses manually
预设选项、动作或手指设置已改变，请重新应用预设，或使用详细流程执行|Preset options, poses, or finger settings changed; reapply the preset or use the detailed workflow
验收通过，可保存副本。|Validation passed; ready to save a copy.
骨架包含动画或驱动数据，需人工检查|Armature has animation or driver data; manual inspection required
骨架父链存在循环|Armature parent chain contains a cycle
骨骼带有约束|Bone has constraints
骨骼配置不完整，请在详细流程重新扫描|Bone configuration is incomplete; rescan in the detailed workflow
，候选删除 |, removal candidates 
，待审核 |, awaiting review 
：已撤销审核。|: approval revoked.
：模式已验收；未知骨角色仍须在骨骼检查中确认。|: mode approved; unknown bone roles still require review.
：没有可确认的同侧手掌映射，不能自动关闭手指|: no confirmed same-side hand mapping; cannot disable fingers automatically
；保留 |; preserve 
；已选中碰撞顶点，等待用户复核，可回退。|; collision vertices selected for review; reverting remains available.
；检查通过。|; checks passed.
；每件独立骨架。|; separate armature for each accessory.
'''

PAIRS += r'''先保存项目或指定绝对输出目录|Save the project or specify an absolute output directory first
动作检查未产生有效运动|Motion validation produced no effective movement
备份失败|Backup failed
总份额不守恒|Total influence share is not conserved
悬空骨骼引用|Dangling bone reference
承重骨禁用变形，需专门处理|A weighted bone has deformation disabled; specialized handling required
无效权重|Invalid weights
有效骨骼权重未规范化；不自动改变动骨份额|Effective bone weights are not normalized; dynamic shares will not be changed automatically
权重映射不一致|Weight mapping mismatch
此对象已清理，不能重复累加权重|Object already processed; weights cannot be accumulated again
没有实际骨骼权重|No actual bone weights
源对象发生变化|Source object changed
源数据已变化，请重新扫描|Source data changed; rescan
网格属性改变: |Mesh attributes changed: 
自定义约束空间尚不支持: |Custom constraint spaces are not supported: 
自有骨静止矩阵发生变化: |Owned bone rest matrix changed: 
饰品动作不一致: |Accessory motion mismatch: 
饰品法线不一致|Accessory normal mismatch
饰品静止外观不一致: |Accessory rest appearance mismatch: 
骨骼集合不一致|Bone set mismatch
承重骨归属不明，请指定自有链或外部挂点: |Weighted bone ownership is unknown; assign an owned chain or external attachment: 
没有有效饰品骨或挂点|No valid accessory bones or attachment points
父级归属未确认，请标记外部挂点或扩展自有链: |Parent ownership is unconfirmed; mark external attachments or extend owned chains: 
父链循环|Parent chain cycle
缺失依赖: |Missing dependency: 
缺失父级: |Missing parent: 
自有链包含外部挂点，需拆分归属: |Owned chain contains external attachments; split ownership: 
配置中包含不存在的骨骼|Configuration contains nonexistent bones
骨名重复|Duplicate bone names
B-Bone 分段蒙皮不支持静止姿态残差补偿|Rest-pose residual compensation does not support segmented B-Bone skinning
保存的清理计划不再匹配输入，不能执行|Saved cleanup plan no longer matches inputs; execution blocked
候选的网格、权重或骨架结构已变化；只允许在此步骤调整 Pose|Candidate mesh, weights, or rig structure changed; only pose edits are allowed at this step
先保存项目，或指定绝对输出目录|Save the project or specify an absolute output directory first
动作检查没有产生任何有效变形|Motion validation produced no effective deformation
只复制本衣物；必要依赖不删除；不会迁移物理运行时|Copy only this garment; preserve required dependencies; do not migrate the physics runtime
备份未成功，不开始修改|Backup failed; no changes started
复制后属性不一致|Attribute mismatch after duplication
复制后求值不一致|Evaluation mismatch after duplication
存在有权重但禁用变形的骨骼，需确认其语义后再处理|Weighted bones have deformation disabled; confirm their semantics before proceeding
存在非有限或负权重，需先修复源数据|Non-finite or negative weights found; repair source data first
左右上臂/前臂/手腕映射不完整；补全映射或关闭自动摆 T pose|Bilateral upper-arm/forearm/wrist mappings are incomplete; complete them or disable automatic T pose
手臂映射不符合上臂→前臂→手腕层级|Arm mapping does not follow upper arm → forearm → wrist hierarchy
手臂映射不能重复|Arm mappings must be unique
摆姿态控制骨有约束，请关闭自动模式并手工摆姿态: |Pose control bones have constraints; disable automatic posing and pose manually: 
检测到形态键/SDEF 数据；第一版不自动烘入或删除，请先专门处理|Shape keys/SDEF detected; this version does not bake or delete them automatically. Process them separately first
此候选已经生成结果，不能重复落实静止姿态|This candidate already has a result; rest pose cannot be applied twice
此对象已有预处理标记，请选原始输入，避免重复烘入|Object is already marked as preprocessed; select the original input to avoid double baking
残差蒙皮矩阵不可稳定求逆|Residual skinning matrix cannot be inverted stably
残差补偿产生非有限坐标|Residual compensation produced non-finite coordinates
残差补偿要求规范化的有效骨骼权重|Residual compensation requires normalized effective bone weights
求值网格为空或含非有限坐标|Evaluated mesh is empty or contains non-finite coordinates
没有已验证的结果可以保存|No validated result to save
清理后动作不一致: |Motion mismatch after cleanup: 
清理后骨骼集合与保留计划不一致|Bone set after cleanup differs from the preservation plan
清理改变了权重或网格属性|Cleanup changed weights or mesh attributes
源对象包含动画/驱动，需先明确处理；不自动删除|Source has animation/drivers; handle these explicitly first. They are not deleted automatically
源对象发生意外变化|Source object changed unexpectedly
源对象或姿态候选已不存在|Source object or pose candidate no longer exists
源对象需处于 Object 模式且无对象约束|Source must be in Object Mode without object constraints
源数据已变化，请重新扫描生成候选|Source data changed; rescan and generate a new candidate
源模型或配置已变化，请重新扫描|Source model or configuration changed; rescan
第一版仅支持无遮挡、顶点组驱动的 LBS；不自动转换 SDEF/DQS|This version supports unmasked vertex-group LBS only; SDEF/DQS are not converted automatically
第一版要求单一 Armature 修改器；其他修改器请先单独处理|This version requires a single Armature modifier; process other modifiers separately first
结果副本保存失败；场景结果保留，可重试保存|Failed to save the result copy; scene results remain available for another save attempt
落实静止姿态后外观发生变化，已撤销候选结果|Appearance changed after applying rest pose; candidate result reverted
衣物没有实际骨骼权重|Garment has no actual bone weights
请将源骨架切换为 Pose Position 后扫描|Set the source armature to Pose Position before scanning
请选择 Object 模式的单件衣物网格|Select one garment mesh in Object Mode
零长度手臂骨: |Zero-length arm bone: 
静止姿态残差补偿未通过真实求值验证|Rest-pose residual compensation failed actual evaluation validation
静止姿态残差超过数值补偿范围，需专门处理骨架|Rest-pose residual exceeds numerical compensation limits; specialized rig handling required
静止姿态转换后仍有非零 Pose basis|Nonzero pose basis remains after rest-pose conversion
静止姿态转换后的法线变化超过 1°，需检查着色|Normals changed by more than 1° after rest-pose conversion; inspect shading
静止姿态转换改变了网格属性|Rest-pose conversion changed mesh attributes
骨约束引用外部对象，需先处理: |Bone constraints reference external objects; handle these first: 
候选末端（可用排除分支覆盖）|Candidate tip (may be overridden by excluded branches)
已确认完整链: |Confirmed complete chain: 
必要依赖: |Required dependency: 
显式保留/解剖参考|Explicit protection/anatomical reference
清理请求包含受保护身体骨、显式保留骨、承重骨或必要依赖，不能删除: |Removal request includes protected body bones, pinned bones, weighted bones, or required dependencies: 
父链循环: |Parent chain cycle: 
用途未确认，默认保留待审核|Purpose unconfirmed; preserved pending review
衣物实际权重|Actual garment weights
身体骨无条件保护: |Body bone unconditionally protected: 
配置骨骼不存在: |Configured bone does not exist: 
骨骼依赖缺失: |Missing bone dependency: 
骨骼父级缺失: |Missing bone parent: 
分片模式不一致或证据不足；需逐片/逐顶点判断|Component modes disagree or evidence is insufficient; review per component or vertex
区域或邻接边界存在归属不明的权重|Region or adjacent boundary has weights with unknown ownership
区域或邻接边界缺少有效权重|Region or adjacent boundary lacks valid weights
存在无效权重|Invalid weights detected
局部跳变过大，缺少连续渐变证据|Local jumps are too large; insufficient evidence of a continuous gradient
拓扑距离层数不足|Insufficient topological distance layers
有效样本过少，需人工判断|Too few valid samples; manual review required
未找到相邻的身体主导连接边缘|No adjacent body-dominated attachment boundary found
波动与连接边缘距离不一致，不能可靠识别渐变|Variation does not follow attachment-boundary distance; gradient classification is unreliable
独立分片样本不足|Insufficient samples in a disconnected component
稳定身体分量与渐变分量叠加，当前算法未覆盖|Stable and graded body components are combined; not covered by the current algorithm
纯动骨分片保持零身体预算，不参与模式投票|Dynamic-only components retain zero body budget and do not vote on mode
纯动骨区域无身体跟随模式；保持零身体预算|Dynamic-only region has no body-follow mode; retain zero body budget
缺少明确的自由端衰减，或存在持续身体跟随底座|No clear free-end decay, or a persistent body-follow component exists
身体与动骨角色冲突|Body and dynamic roles conflict
身体份额及内部骨骼分布稳定|Body share and internal bone distribution are stable
身体影响沿拓扑距离从连接边缘衰减|Body influence decays with topological distance from the attachment boundary
顶点范围无效|Invalid vertex scope
7 个标准训练动作与 4 个独立验证动作|7 standard training poses and 4 held-out validation poses
A 副本或姿态已变更，请重新生成 A|A copy or pose changed; regenerate A
从 JSON 读取骨骼、鞋带审核、方向和动作；保留原对象，输出对照副本|Read bones, lace reviews, directions, and poses from JSON; preserve originals and output comparison copies
使用文件中的姿态设置|Use pose settings from file
保留 JSON 中的 poses 或 pose_preset|Preserve poses or pose_preset from JSON
加载审核配置，生成平底鞋 A/B|Load reviewed configuration and generate flat-shoe A/B copies
原生采样 → 延伸 → 连续性 → 间距对照|Native sampling → extension → continuity → gap comparison
复杂网格平底鞋（审核配置）|Complex Flat Shoes (Reviewed Configuration)
平底鞋标准 + 随机辅助|Flat-shoe standard + random auxiliary poses
平底鞋结果：|Flat-shoe results: 
每姿态相对权重|Relative weight per pose
输入网格、权重或姿态已变更，请重新生成 A|Input mesh, weights, or pose changed; regenerate A
采样或区域配置已变更，请重新生成 A|Sampling or region configuration changed; regenerate A
随机总权重最多为标准总权重的 20%|Total random weight is capped at 20% of standard pose weight
需审核鞋带与骨骼配置；高跟鞋不适用|Review lace and bone settings first; high heels are not supported
鞋子姿态|Shoe poses
；报告：|; report: 
'''

ZH_TO_EN = dict(line.split('|', 1) for line in PAIRS.splitlines() if '|' in line)

TEMPLATES = {'Owned/dependent {v0} bones; fixed attachments {v1}; separate armature for each accessory.': '自有/依赖 {v0} 骨；固定挂点 {v1}；每件独立骨架。', 'Removed {v0} bones; armature data backup: {v1}': '已清理 {v0} 根骨骼；骨架数据备份：{v1}', 'Checked {v0} bound meshes (including hidden meshes), {v1} root chains eligible for removal.': '检查了 {v0} 个绑定网格（含隐藏网格），{v1} 条根链可清理。', '{v0}（{v1} bones)': '{v0}（{v1} 骨）', '{v0} bones → preserve {v1}, removal candidates {v2}, awaiting review {v3}': '{v0} 骨 → 保留 {v1}，候选删除 {v2}，待审核 {v3}', 'Ready for editing: {v0} bones; preserve {v1} constraints.': '编辑就绪：{v0} 骨；保留 {v1} 个约束。', 'Scan complete: {v0} source groups, {v1} lace regions awaiting review': '扫描完成：{v0} 个源组，{v1} 个待审核鞋带区域', 'Checks passed: {v0} training / {v1} validation poses': '检查通过：{v0} 个训练 / {v1} 个验证姿态', 'Effective random weight: {v0:.3f} per pose; total capped at 1.4': '随机实际权重 {v0:.3f}/个；总量上限 1.4', 'Gap RMS: A {v0:.6g} / B {v1:.6g}': '间距 RMS：A {v0:.6g} / B {v1:.6g}', 'Scan complete: generated {v0} candidate root regions; confirm dynamic roles and body-follow modes.': '扫描完成：生成 {v0} 个根骨候选区域；请确认动骨身份及身体跟随模式。', 'Classification: uniform {v0}, gradient {v1}, unrecognized {v2}; preserve {v3} approved entries. Review each region.': '粗识别：均匀 {v0}、渐变 {v1}、无法识别 {v2}；保留 {v3} 个已验收项。请逐区验收。', 'Added {v0} preset poses; existing poses preserved.': '已补充 {v0} 条预设动作；已有动作保留。', 'Captured {v0} vertices; exit Edit Mode before solving.': '已记录 {v0} 个顶点；计算前请退出编辑模式。', 'Highlight {v0} source vertices; adjust the selection and capture again if needed.': '高亮 {v0} 个源顶点；可修正选区后重新记录。', 'Six-class preview complete: {v0} vertices; fallback {v1} vertices. Ready to write an initialization copy.': '六类预览完成：{v0} 顶点；回退 {v1} 顶点。可写入独立初值副本。', ' held-out pose RMS {v0:.6g} → {v1:.6g}': ' 独立姿态 RMS {v0:.6g} → {v1:.6g}', 'Selected {v0} collision-related vertices; the report distinguishes existing, new, and worsened collisions.': '已选中 {v0} 个碰撞相关顶点；报告保留既有、新增及恶化情况。', 'Configuration passed: {v0} region vertices; all effective source deformation contributions are preserved.': '配置通过：{v0} 个区域顶点；有效源变形贡献将全部保留。', 'Scope: explicit selection, {v0} vertices': '范围：显式选区 {v0} 个顶点', 'Mean {v0:.4f}  Variance {v1:.6f}': '均值 {v0:.4f}  方差 {v1:.6f}', 'Range {v0:.4f}  Relative range {v1:.3f}': '极差 {v0:.4f}  相对极差 {v1:.3f}', 'Configured: {v0} poses': '已配置 {v0} 个动作', 'Core vertices: {v0}': '核心顶点：{v0}', '{v0} Arm raise': '{v0} 抬臂', '{v0} Arm swing': '{v0} 前后摆臂', '{v0} Elbow bend': '{v0} 屈肘', '{v0} Leg raise': '{v0} 抬腿', '{v0} Leg abduction': '{v0} 腿外展', '{v0} Knee bend': '{v0} 屈膝', '{v0} Wrist twist': '{v0} 手腕扭转', '{v0} Wrist bend': '{v0} 手腕弯曲', '{v0} Wrist tilt': '{v0} 手腕侧偏'}

def format_message(template, **values):
    try:
        from bpy.app.translations import pgettext_iface
    except ImportError:
        return template.format(**values)
    return pgettext_iface(template).format(**values)

TEMPLATES.update({})
