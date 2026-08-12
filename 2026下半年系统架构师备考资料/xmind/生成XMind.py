#!/usr/bin/env python3
"""从本工作区官方教程的拆分 PDF 生成可审查 Markdown 与原生 XMind 文件。"""
from __future__ import annotations

import json
import re
import shutil
import sys
import uuid
import zipfile
from pathlib import Path

from pypdf import PdfReader

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
SPLIT = REPO / "按章节拆分"
OUT = BASE / "系统架构设计师-全量知识点.xmind"
SOURCES = BASE / "源稿"
BUILD = BASE / ".build"
# 拆分集未包含完整教程的第 1 页封面；00-前言对应物理页 2 起。
FIRST_SPLIT_PHYSICAL_PAGE = 2
EXPECTED_BOOK_PAGES = 720

CHAPTERS = [
    (1, "绪论"), (2, "计算机系统基础知识"), (3, "信息系统基础知识"),
    (4, "信息安全技术基础知识"), (5, "软件工程基础知识"), (6, "数据库设计基础知识"),
    (7, "系统架构设计基础知识"), (8, "系统质量属性与架构评估"),
    (9, "软件可靠性基础知识"), (10, "软件架构的演化和维护"),
    (11, "未来信息综合技术"), (12, "信息系统架构设计理论与实践"),
    (13, "层次式架构设计理论与实践"), (14, "云原生架构设计理论与实践"),
    (15, "面向服务架构设计理论与实践"), (16, "嵌入式系统架构设计理论与实践"),
    (17, "通信系统架构设计理论与实践"), (18, "安全架构设计理论与实践"),
    (19, "大数据架构设计理论与实践"), (20, "系统架构设计师论文写作要点"),
]

# 给每个一级节补一条可复习的机制性要点；编号标题本身从教材自动提取，保证目录层级覆盖。
SECTION_NOTES = {
"1.1":"掌握系统/软件架构的定义、发展、分类、建模和适用场景。",
"1.2":"架构师要把需求、约束、技术方案、文档、评估和沟通协调起来。",
"1.3":"优秀架构师兼具技术深度、系统思维、权衡能力、业务理解和工程实践。",
"2.1":"系统由硬件、软件、网络、数据和人员等要素协同构成。",
"2.2":"掌握 CPU、存储、总线、接口和外设的组成、层次与性能影响。",
"2.3":"理解操作系统、数据库、文件、协议、中间件、构件和应用软件的职责边界。",
"2.4":"嵌入式系统要兼顾专用性、实时性、资源约束和安全攸关特性。",
"2.5":"网络复习按概念、通信、网络、组网与工程五层组织，关注协议和可用性。",
"2.6":"掌握语言构成、语言范型和编译/解释等基本分类。",
"2.7":"多媒体关注媒体类型、编码压缩、同步和关键处理技术。",
"2.8":"系统工程以整体、生命周期和模型化方法管理复杂系统。",
"2.9":"性能题围绕指标、计算、设计优化与评估展开。",
"3.1":"信息系统要掌握定义、发展、分类、生命周期、建设原则与开发方法。",
"3.2":"TPS 面向日常业务交易，强调及时、准确、可靠和高吞吐。",
"3.3":"MIS 将业务数据转化为管理信息，支持计划、控制和决策。",
"3.4":"DSS 以模型、数据和交互支持半结构化或非结构化决策。",
"3.5":"专家系统由知识库、推理机、解释机制和人机接口等组成。",
"3.6":"OAS 用于办公流程、文档、通信和协同自动化。",
"3.7":"ERP 集成企业资源与流程，核心是统一数据和计划控制。",
"3.8":"结合政务、企业、电子商务的行业特征选择信息系统架构。",
"4.1":"信息安全以保密性、完整性、可用性为基础，覆盖存储与网络安全。",
"4.2":"安全的价值在于保护资产、保障业务连续性并满足法律合规要求。",
"4.3":"安全体系必须同时覆盖技术、组织机构和管理制度。",
"4.4":"区分对称/非对称加密的密钥、效率、分发与典型用途。",
"4.5":"密钥生命周期包括产生、分配、存储、使用、更新、撤销与销毁。",
"4.6":"访问控制要区分主体、客体、授权模型；签名解决完整性、认证和抗抵赖。",
"4.7":"针对拒绝服务、欺骗、扫描、漏洞等攻击给出检测、加固与响应措施。",
"4.8":"等级保护与风险管理以资产、威胁、脆弱性、风险和控制为主线。",
"5.1":"比较瀑布、迭代、敏捷、RUP、成熟度模型的适用条件和管理重点。",
"5.2":"需求工程包括获取、分析、规格说明、验证、变更和追踪。",
"5.3":"区分结构化和面向对象的分析设计工件、方法与建模视角。",
"5.4":"测试按方法和阶段组织，重视测试覆盖、缺陷定位和回归。",
"5.5":"净室工程强调形式化规约、正确性验证和统计测试。",
"5.6":"CBSE 关注构件模型、获取/开发、组装、适配和复用。",
"5.7":"项目管理覆盖范围、进度、配置、质量、风险与持续监控。",
"6.1":"掌握数据模型、DBMS 功能和三级模式两级映像的数据独立性。",
"6.2":"关系模型复习关系运算、函数依赖、范式、键与完整性约束。",
"6.3":"数据库设计按需求、概念、逻辑、物理、实施和维护逐步展开。",
"6.4":"应用访问数据库要比较库函数、嵌入 SQL、通用接口和 ORM。",
"6.5":"NoSQL 按键值、列族、文档、图等分类，权衡一致性、扩展性和查询能力。",
"7.1":"软件架构关注构件、连接件、约束及其与生命周期的关系。",
"7.2":"ABSD 从需求、设计、文档、复审、实现到演化形成闭环。",
"7.3":"架构风格按数据流、调用返回、数据中心、虚拟机、独立构件比较。",
"7.4":"架构复用明确复用对象、形式、过程、收益与适配成本。",
"7.5":"DSSA 通过领域分析、领域设计和领域实现建设可复用体系结构。",
"8.1":"质量属性必须写成可度量的场景：刺激、环境、响应和响应度量。",
"8.2":"评估关注风险点、敏感点、权衡点和利益相关者目标。",
"8.3":"ATAM 分演示、调查分析、测试和报告，产出风险主题与改进项。",
"9.1":"掌握可靠性、失效、故障、MTTF/MTTR/MTBF、可用度与测试含义。",
"9.2":"可靠性模型需基于运行剖面、失效数据和适用假设选择。",
"9.3":"可靠性管理贯穿目标制定、过程控制、度量、评审和改进。",
"9.4":"设计策略包括容错、检错、降低复杂度和系统配置。",
"9.5":"可靠性测试先定义运行剖面，再设计用例、实施并收集失效数据。",
"9.6":"评价包括模型选择、数据收集、评估预测和结果解释。",
"10.1":"演化源于需求、环境和定义变化，架构定义应支持可演化性。",
"10.2":"面向对象演化可从对象、消息、复合片段和约束四类分析。",
"10.3":"区分静态/动态演化及其不同时期的特点与风险。",
"10.4":"演化遵循可追踪、渐进、兼容、可验证和风险受控原则。",
"10.5":"已知演化过程和未知演化过程需采用不同评估方法。",
"10.6":"网站演化主线：单体、垂直、缓存、集群、读写分离、CDN、分布式、拆分、服务化。",
"10.7":"维护通过知识、修改、版本和可维护性度量降低技术债。",
"11.1":"CPS 融合计算、通信和物理过程，关注感知、控制、反馈和安全。",
"11.2":"AI 复习概念、历史、机器学习、知识表示、推理、感知等关键技术。",
"11.3":"机器人涵盖感知、决策、控制、执行及其智能化分类。",
"11.4":"边缘计算强调近端处理、低时延、边云协同、资源管理和安全。",
"11.5":"数字孪生以物理实体、虚拟模型、数据连接和服务闭环为核心。",
"11.6":"云计算与大数据分别关注服务化弹性资源和海量多样数据处理。",
"12.1":"信息系统架构经历从技术实现到业务、数据、应用、技术协同的发展。",
"12.2":"区分物理/逻辑结构、架构风格、分类、原理、模型和企业总体框架。",
"12.3":"架构设计可采用 ADM 与信息化总体架构方法，自顶向下分解落地。",
"12.4":"案例用价值驱动、Web 服务和企业整合展示架构决策。",
"13.1":"分层架构以职责分离、依赖控制、高内聚低耦合为核心。",
"13.2":"表现层关注 MVC/UIP、交互流程、视图一致性和动态生成。",
"13.3":"中间层组织业务组件、工作流、实体和业务框架。",
"13.4":"数据访问层关注访问模式、工厂/ORM、事务、连接和 Schema。",
"13.5":"数据架构要协调数据库、对象模型与 XML 表示。",
"13.6":"物联网层次通常包括感知、网络、平台/应用等层及其接口。",
"13.7":"案例检验分层职责、访问边界、事务与部署设计。",
"14.1":"云原生出现于弹性、敏捷交付、规模化运维与云基础设施发展背景。",
"14.2":"原则包括服务化、弹性、可观测、自动化、韧性；同时识别反模式。",
"14.3":"关键技术为容器、微服务、无服务器、服务网格及其治理能力。",
"14.4":"改造案例关注迁移路径、组织流程、平台能力、风险和量化成效。",
"15.1":"SOA 以服务契约和业务流程为中心，BPEL 用于服务编排。",
"15.2":"理解 SOA 演进、国内外差异及与微服务的继承和区别。",
"15.3":"参考架构明确消费者、服务、注册库、总线、治理等角色。",
"15.4":"区分 UDDI、WSDL、SOAP、REST 的定位、格式和使用场景。",
"15.5":"SOA 标准化涵盖文档、协议、统一登记集成和 QoS。",
"15.6":"SOA 的收益是复用、集成、敏捷和业务/IT 对齐，也有治理成本。",
"15.7":"设计原则包括松耦合、粗粒度、无状态、可组合、可发现和标准化。",
"15.8":"重点模式：注册表、ESB、微服务；说明职责和适用边界。",
"15.9":"实施要处理遗留集成、服务粒度、状态、性能、安全和治理问题。",
"15.10":"SOA 过程从方案选择、流程分析、服务识别、设计、实施到治理。",
"16.1":"嵌入式系统由硬件平台、操作系统、驱动、中间件和应用组成。",
"16.2":"典型模式、嵌入式 OS/DB/中间件和开发环境受实时与资源约束影响。",
"16.3":"采用 ABSD、属性驱动设计和实时系统方法处理性能、可靠性与时限。",
"16.4":"案例关注操作系统分层、安全攸关和物联网 OS 的架构要点。",
"17.1":"通信系统由信源、信道、信宿及协议控制等构成。",
"17.2":"分别掌握 LAN、WAN、移动网、存储网、SDN 的架构与关键设备。",
"17.3":"关键技术围绕高可用、IPv4/IPv6 双栈和 SDN 控制转发分离。",
"17.4":"网络设计先需求分析，再技术选型、方案设计、安全与绿色设计。",
"17.5":"案例用于训练高可用、双栈园区、5G 应用的约束与方案。",
"18.1":"安全架构从威胁、范围、标准组织和资产保护目标出发。",
"18.2":"掌握状态机、Biba、Clark-Wilson、Chinese Wall 等模型的保护目标。",
"18.3":"安全规划由技术体系、管理体系、组织体系和实施路线组成。",
"18.4":"WPDRRC：预警、保护、检测、响应、恢复、反击/追踪，形成闭环。",
"18.5":"网络安全框架覆盖认证、访问控制、机密性、完整性和抗抵赖。",
"18.6":"数据库安全含评估、访问控制、审计、备份恢复与完整性。",
"18.7":"脆弱性分析识别软件缺陷、攻击面和典型架构的薄弱环节。",
"18.8":"案例将威胁映射到纵深防御、身份、数据、审计和应急措施。",
"19.1":"传统处理在规模、速度、类型、实时性和扩展性方面面临瓶颈。",
"19.2":"大数据架构需处理采集、存储、计算、服务、治理和弹性挑战。",
"19.3":"Lambda 以批处理层、速度层、服务层平衡准确性和实时性。",
"19.4":"Kappa 以流处理为中心，简化为单一处理路径但依赖可重放日志。",
"19.5":"选型比较实时性、复杂度、数据修正、运维成本和团队能力。",
"19.6":"案例关注业务指标、数据链路、处理模式、服务输出和演进。",
"20.1":"考前准备包括素材、主题、练习、格式和机考输入；按要求排版。",
"20.2":"解题按审题、选项目、列提纲、展开、检查执行。",
"20.3":"摘要写项目和核心措施；正文以本人角色、决策、实施、效果为主线。",
"20.4":"避免跑题、空泛、虚构、结构失衡、角色不清和技术错误。",
}

EXAM_TREE = {
    "综合知识（选择题）": [
        "基础：计算机系统、信息系统、安全、软件工程、数据库",
        "架构：风格、质量属性、评估、可靠性、演化",
        "专题：云原生、SOA、嵌入式、通信、安全、大数据、未来技术",
        "答题：概念边界、指标公式、适用条件、优缺点与标准术语",
    ],
    "案例分析（问答题）": [
        "审题：业务目标、规模、约束、现状、风险和每问动作词",
        "作答：问题/风险 → 机制/措施 → 代价/边界 → 验证",
        "高频：质量属性、架构选型、分层/服务治理、安全、演化、数据处理",
        "复盘：按得分点记录漏答、审题错误、概念错误和表达错误",
    ],
    "论文（论文题）": [
        "真实项目：背景、角色、约束、规模、数据与业务目标",
        "架构论证：总体结构 + 3至4项关键决策、取舍、实现和验证",
        "治理：测试、监控、发布、回滚、安全、成本和持续演化",
        "收束：量化效果、问题反思；避免空泛定义和虚构经历",
    ],
}


def uid() -> str:
    return uuid.uuid4().hex


def find_pdf(chapter: int) -> Path:
    files = sorted(SPLIT.glob(f"{chapter:02d}-*.pdf"))
    if len(files) != 1:
        raise RuntimeError(f"第 {chapter} 章 PDF 不唯一：{files}")
    return files[0]


def physical_page_ranges() -> dict[Path, tuple[int, int]]:
    """按拆分 PDF 顺序还原教程的 1 基物理页范围。"""
    result = {}
    first_page = FIRST_SPLIT_PHYSICAL_PAGE
    for pdf in sorted(SPLIT.glob("[0-9][0-9]-*.pdf")):
        pages = len(PdfReader(pdf).pages)
        last_page = first_page + pages - 1
        result[pdf.resolve()] = (first_page, last_page)
        first_page = last_page + 1
    if first_page - 1 != EXPECTED_BOOK_PAGES:
        raise RuntimeError(f"拆分 PDF 物理页结束错误：{first_page - 1}")
    return result


def clean_title(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"\s*[·.。…]+\s*\d+\s*$", "", value)
    return value.strip(" -–—")


def extract_outline(chapter: int, pdf: Path):
    reader = PdfReader(pdf)
    lines = []
    seen = set()
    pattern = re.compile(rf"^{chapter}\.(\d+)(?:\.(\d+))?\s*(.+)$")
    for page in reader.pages:
        for raw in (page.extract_text() or "").splitlines():
            raw = raw.strip()
            match = pattern.match(raw)
            if not match:
                continue
            second, third, title = match.groups()
            title = clean_title(title)
            if len(title) < 2 or len(title) > 70 or re.fullmatch(r"[\d.]+", title):
                continue
            code = f"{chapter}.{second}" + (f".{third}" if third else "")
            # 每个教材编号只保留正文中首次出现的短标题，避免正文引用被误认为目录。
            if code not in seen:
                seen.add(code)
                lines.append((code, title, 3 if third else 2))
    if not lines:
        raise RuntimeError(f"未从 {pdf.name} 提取到目录标题")
    details = extract_section_details(chapter, reader, lines)
    return reader, lines, details


def normalize_paragraph(value: str) -> str:
    value = re.sub(r"\s+", "", value).strip()
    if len(value) < 16 or re.fullmatch(r"[\d.]+", value):
        return ""
    # 排除页眉、页脚和主要由图表数字组成的噪声；保留正常技术说明中的数字。
    if "系统架构设计师教程" in value or "第" in value and "章" in value and len(value) < 25:
        return ""
    if sum(ch.isdigit() for ch in value) / max(len(value), 1) > 0.45:
        return ""
    return value


def split_sentences(value: str):
    """把提取出的长段按句子切开，供备注以列表展示。"""
    chunks = re.split(r"(?<=[。！？；])", value)
    return [x.strip() for x in chunks if len(x.strip()) >= 12]


def compact_note(paragraph: str) -> str:
    """XMind 备注保留原始提取内容，但按结论、段落、列表排版。"""
    sentences = split_sentences(paragraph)
    if not sentences:
        return "**教材原文要点**\n\n- 未能按句分割；请结合源 PDF 复核。\n\n**复习提示**\n\n- 用“定义、机制、适用条件、代价”四项主动回忆。"
    conclusion = sentences[0]
    remaining = sentences[1:]
    if not remaining and len(conclusion) > 70:
        clauses = [x.strip() for x in re.split(r"(?<=[，、：])", conclusion) if len(x.strip()) >= 8]
        conclusion = clauses[0] if clauses else conclusion
        remaining = clauses[1:]
    lines = ["**核心结论**", "", conclusion, "", "**教材原文要点**", ""]
    if remaining:
        lines += [f"- {item}" for item in remaining]
    else:
        lines.append("- 本段仅含一个完整句子；核心结论即为全文要点。")
    lines += ["", "**复习提示**", "", "- 用“定义、机制、适用条件、代价”四项主动回忆。"]
    return "\n".join(lines)


def extract_section_details(chapter: int, reader, outline):
    """按已验证的编号标题切分每段文字；每段作为可折叠节点，全文放入备注。"""
    codes = {code for code, _, _ in outline}
    title_by_code = {code: title for code, title, _ in outline}
    start_re = re.compile(rf"^({chapter}\.\d+(?:\.\d+)?)\s*(.*)$")
    raw_by_code = {code: [] for code in codes}
    current = None
    for page in reader.pages:
        for raw in (page.extract_text() or "").splitlines():
            stripped = raw.strip()
            match = start_re.match(stripped)
            if match and match.group(1) in codes:
                current = match.group(1)
                tail = normalize_paragraph(match.group(2))
                # 标题行末尾的正文偶尔与标题相连；标题本身不重复收集。
                if tail and tail != title_by_code[current].replace(" ", ""):
                    raw_by_code[current].append(tail)
                continue
            if current is None:
                continue
            cleaned = normalize_paragraph(stripped)
            if cleaned:
                raw_by_code[current].append(cleaned)
            elif not stripped:
                raw_by_code[current].append("")

    details = {}
    for code, raw_lines in raw_by_code.items():
        paragraphs, bucket, seen = [], [], set()
        for line in raw_lines + [""]:
            if line:
                bucket.append(line)
                continue
            if not bucket:
                continue
            paragraph = normalize_paragraph("".join(bucket))
            bucket = []
            if not paragraph or paragraph in seen:
                continue
            # 避免将下一页重复的节标题或长目录行作为正文要点。
            if paragraph.startswith(code.replace(" ", "")) or paragraph == title_by_code[code].replace(" ", ""):
                continue
            seen.add(paragraph)
            paragraphs.append(paragraph)
        details[code] = paragraphs
    return details


def topic(title: str, children=None, note: str | None = None, structure: str | None = None):
    data = {"id": uid(), "class": "topic", "title": title}
    if children:
        data["children"] = {"attached": children}
    if note:
        data["notes"] = {"plain": {"content": note}}
    if structure:
        data["structureClass"] = structure
    return data


def detail_topics(paragraphs):
    items = []
    for idx, paragraph in enumerate(paragraphs, start=1):
        brief = paragraph[:34] + ("…" if len(paragraph) > 34 else "")
        items.append(topic(f"要点 {idx}：{brief}", note=compact_note(paragraph)))
    return items


def chapter_tree(chapter: int, name: str, pdf: Path, page_range: tuple[int, int]):
    reader, outline, details = extract_outline(chapter, pdf)
    first_page, last_page = page_range
    root = topic(
        f"第{chapter}章 {name}",
        note=f"**教材来源**\n\n- `{pdf.relative_to(REPO)}`\n- PDF 物理页范围：{first_page}–{last_page}（本章 {len(reader.pages)} 页）\n\n**节点来源**\n\n- 目录节点来自该范围的教材 PDF 文字层。\n- 展开“复习要点”和“教材正文要点”进行主动回忆。",
        structure="org.xmind.ui.logic.right",
    )
    sections = {}
    ordered = []
    for code, title, level in outline:
        if level == 2:
            node = topic(f"{code} {title}")
            sections[code] = node
            ordered.append(node)
        else:
            parent = f"{chapter}.{code.split('.')[1]}"
            if parent not in sections:
                node = topic(parent)
                sections[parent] = node
                ordered.append(node)
            child = topic(f"{code} {title}")
            child_details = detail_topics(details.get(code, []))
            if child_details:
                child["children"] = {"attached": [topic(f"教材正文要点（{len(child_details)}条）", child_details)]}
            sections[parent].setdefault("children", {"attached": []})["attached"].append(child)
    for code, node in sections.items():
        note = SECTION_NOTES.get(code)
        if note:
            node.setdefault("children", {"attached": []})["attached"].insert(0, topic(f"复习要点：{note}"))
        section_details = detail_topics(details.get(code, []))
        if section_details:
            node.setdefault("children", {"attached": []})["attached"].append(topic(f"教材正文要点（{len(section_details)}条）", section_details))
    root["children"] = {"attached": ordered}
    return root, outline, details, len(reader.pages)


def markdown_outline(chapter: int, name: str, pdf: Path, outline, details, pages: int, page_range: tuple[int, int]) -> str:
    first_page, last_page = page_range
    source = f"> 来源：`{pdf.relative_to(REPO)}`；PDF 物理页范围：{first_page}–{last_page}（本章 {pages} 页）。"
    result = [f"# 第{chapter}章 {name}", "", source, "", "## 知识结构"]
    current_section = None
    for code, title, level in outline:
        if level == 2:
            current_section = code
            result += [f"\n### {code} {title}"]
            if code in SECTION_NOTES:
                result.append(f"- 复习要点：{SECTION_NOTES[code]}")
            for paragraph in details.get(code, []):
                result.append(f"- 教材正文：{paragraph}")
        else:
            result.append(f"- {code} {title}")
            for paragraph in details.get(code, []):
                result.append(f"  - 教材正文：{paragraph}")
    result += ["", "## 使用提示", "- 导图保留教材可识别的编号标题；图、表、例题和长段正文不逐字复制。", "- 每个一级节的“复习要点”用于主动回忆；答不出时回到对应 PDF 阅读。"]
    return "\n".join(result) + "\n"


def overview_sheet(chapter_roots):
    groups = [
        ("基础与通识（第1–6章）", ["第1章 架构师与系统架构", "第2章 计算机系统", "第3章 信息系统", "第4章 信息安全", "第5章 软件工程", "第6章 数据库"]),
        ("架构核心（第7–10章）", ["第7章 架构设计", "第8章 质量与评估", "第9章 可靠性", "第10章 演化维护"]),
        ("未来与综合（第11章）", ["第11章 CPS、AI、机器人、边缘、数字孪生、云和大数据"]),
        ("专题架构（第12–19章）", ["信息系统", "层次式", "云原生", "SOA", "嵌入式", "通信", "安全", "大数据"]),
        ("考试输出（第20章）", ["综合知识", "案例分析", "论文写作"]),
    ]
    children = [topic(title, [topic(x) for x in nodes]) for title, nodes in groups]
    root = topic("系统架构设计师：全量知识总览", children, "**工作簿内容**\n\n- 20 章教材导图\n- 1 张三科输出图\n\n**使用建议**\n\n- 先总览定位，再进入章节 sheet 细读。", structure="org.xmind.ui.logic.right")
    return {"id": uid(), "class": "sheet", "title": "00-总体知识总览", "rootTopic": root}


def exam_sheet():
    root = topic("知识点到三科输出", [topic(k, [topic(x) for x in v]) for k, v in EXAM_TREE.items()], "**考试形式**\n\n- 综合知识：选择题\n- 案例分析：问答题\n- 论文：论文题\n\n**共同要求**\n\n- 三科均为计算机化考试。", structure="org.xmind.ui.logic.right")
    return {"id": uid(), "class": "sheet", "title": "21-知识点到三科输出", "rootTopic": root}


def write_xmind(sheets):
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)
    (BUILD / "content.json").write_text(json.dumps(sheets, ensure_ascii=False, indent=2), encoding="utf-8")
    metadata = {"creator": {"name": "Codex"}, "createdTime": "2026-08-04T00:00:00Z", "modifiedTime": "2026-08-04T00:00:00Z"}
    (BUILD / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {"file-entries": {"content.json": {}, "metadata.json": {}}}
    (BUILD / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(BUILD.iterdir()):
            archive.write(path, path.name)


def count_topics(item):
    total = 1
    for child in item.get("children", {}).get("attached", []):
        total += count_topics(child)
    return total


def generate():
    SOURCES.mkdir(parents=True, exist_ok=True)
    page_ranges = physical_page_ranges()
    sheets = []
    chapter_sheets = []
    for chapter, name in CHAPTERS:
        pdf = find_pdf(chapter)
        page_range = page_ranges[pdf.resolve()]
        root, outline, details, pages = chapter_tree(chapter, name, pdf, page_range)
        source_name = f"{chapter:02d}-{name}.md"
        source_text = markdown_outline(chapter, name, pdf, outline, details, pages, page_range)
        (SOURCES / source_name).write_text(source_text, encoding="utf-8")
        chapter_sheets.append({"id": uid(), "class": "sheet", "title": f"{chapter:02d}-第{chapter}章{name}", "rootTopic": root})
    sheets.append(overview_sheet(chapter_sheets))
    sheets.extend(chapter_sheets)
    sheets.append(exam_sheet())
    write_xmind(sheets)
    validate()


def validate():
    with zipfile.ZipFile(OUT) as archive:
        required = {"content.json", "metadata.json", "manifest.json"}
        names = set(archive.namelist())
        if not required <= names:
            raise RuntimeError(f"XMind 缺少文件：{required - names}")
        try:
            content_text = archive.read("content.json").decode("utf-8", errors="strict")
            archive.read("metadata.json").decode("utf-8", errors="strict")
            archive.read("manifest.json").decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise RuntimeError(f"XMind 包含非 UTF-8 文件：{error}") from error
        sheets = json.loads(content_text)
    if len(sheets) != 22:
        raise RuntimeError(f"工作表数量错误：{len(sheets)}")
    titles = [sheet["title"] for sheet in sheets]
    chapter_titles = [x for x in titles if re.match(r"^\d{2}-第\d+章", x)]
    if len(chapter_titles) != 20:
        raise RuntimeError(f"章节工作表数量错误：{len(chapter_titles)}")
    chapter_sheets = [sheet for sheet in sheets if re.match(r"^\d{2}-第\d+章", sheet["title"])]
    page_ranges = physical_page_ranges()
    for (chapter, name), sheet in zip(CHAPTERS, chapter_sheets):
        expected_root = f"第{chapter}章 {name}"
        root = sheet["rootTopic"]
        if root.get("title") != expected_root:
            raise RuntimeError(f"根节点与章节不一致：{sheet['title']} -> {root.get('title')}")
        note = root.get("notes", {}).get("plain", {}).get("content", "")
        first_page, last_page = page_ranges[find_pdf(chapter).resolve()]
        expected_range = f"物理页范围：{first_page}–{last_page}"
        if "教材来源" not in note or "节点来源" not in note or expected_range not in note:
            raise RuntimeError(f"章节备注缺少来源或物理页范围：{sheet['title']}")
    empty = [sheet["title"] for sheet in sheets if count_topics(sheet["rootTopic"]) < 2]
    if empty:
        raise RuntimeError(f"空导图：{empty}")
    source_files = sorted(SOURCES.glob("*.md"))
    if len(source_files) != 20:
        raise RuntimeError(f"源稿数量错误：{len(source_files)}")
    for chapter, name in CHAPTERS:
        source_path = SOURCES / f"{chapter:02d}-{name}.md"
        source_text = source_path.read_text(encoding="utf-8", errors="strict")
        expected_root = f"# 第{chapter}章 {name}"
        first_page, last_page = page_ranges[find_pdf(chapter).resolve()]
        if not source_text.startswith(expected_root) or f"物理页范围：{first_page}–{last_page}" not in source_text:
            raise RuntimeError(f"源稿根标题或物理页范围与导图不一致：{source_path.name}")
    required_terms = {"ATAM", "云原生", "SOA", "WPDRRC", "Lambda", "Kappa"}
    missing_terms = sorted(term for term in required_terms if term not in content_text)
    if missing_terms:
        raise RuntimeError(f"XMind 缺少关键术语：{missing_terms}")
    total = sum(count_topics(sheet["rootTopic"]) for sheet in sheets)
    print(json.dumps({"sheets": len(sheets), "chapter_sheets": len(chapter_titles), "source_markdown": len(source_files), "topics": total, "xmind": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--validate":
        validate()
    else:
        generate()
