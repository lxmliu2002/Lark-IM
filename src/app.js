const STORAGE_KEY = "agent-pilot-public-demo-state";
const CHANNEL_KEY = "agent-pilot-public-demo-channel";

const SCENE_DEFS = [
  {
    key: "A",
    title: "意图/指令入口",
    desc: "从 IM 群聊或单聊捕捉文本与语音指令。",
  },
  {
    key: "B",
    title: "任务理解与规划",
    desc: "拆解目标、依赖、输出物与确认点。",
  },
  {
    key: "C",
    title: "文档/白板生成与编辑",
    desc: "沉淀需求、方案、风险与行动项。",
  },
  {
    key: "D",
    title: "演示稿生成与排练",
    desc: "把文档结构化为汇报页并生成讲稿提示。",
  },
  {
    key: "E",
    title: "多端协作与一致性",
    desc: "同步状态、内容、离线队列与合并结果。",
  },
  {
    key: "F",
    title: "总结与交付",
    desc: "生成归档摘要、分享链接与导出清单。",
  },
];

const TABS = [
  { key: "doc", label: "Doc" },
  { key: "canvas", label: "Canvas" },
  { key: "slides", label: "Slides" },
  { key: "delivery", label: "Ship" },
];

const devices = {
  desktop: {
    label: "桌面端",
    online: true,
    thread: "群聊",
    activeTab: "doc",
    queue: [],
    state: null,
  },
  mobile: {
    label: "移动端",
    online: true,
    thread: "群聊",
    activeTab: "doc",
    queue: [],
    state: null,
  },
};

let serverState = loadState();
let timers = [];
let channel = null;

function createInitialState() {
  const now = new Date().toISOString();
  return {
    rev: 1,
    updatedAt: now,
    appliedOps: [],
    chat: [
      {
        id: uid("msg"),
        author: "产品经理",
        role: "peer",
        thread: "群聊",
        text: "下周评审需要把智能客服升级方案整理成文档和汇报材料。",
        at: now,
      },
      {
        id: uid("msg"),
        author: "设计负责人",
        role: "peer",
        thread: "群聊",
        text: "方案里要体现移动端、桌面端切换，以及人工接管后的状态一致性。",
        at: now,
      },
      {
        id: uid("msg"),
        author: "销售负责人",
        role: "peer",
        thread: "群聊",
        text: "客户还关心 ROI、上线风险和三阶段推进计划。",
        at: now,
      },
    ],
    task: {
      title: "等待 IM 指令",
      status: "idle",
      currentStep: "Scene A",
      progress: 0,
    },
    scenes: Object.fromEntries(
      SCENE_DEFS.map((scene) => [scene.key, { status: "pending", updatedAt: now }]),
    ),
    plan: [],
    doc: {
      title: "未生成文档",
      updatedAt: now,
      blocks: [],
    },
    canvas: {
      cards: [],
    },
    slides: [],
    rehearsal: {
      totalMinutes: 0,
      notes: [],
    },
    delivery: {
      title: "未交付",
      link: "",
      archiveId: "",
      summary: "",
      assets: [],
      updatedAt: now,
    },
    activity: [],
  };
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return createInitialState();
    const parsed = JSON.parse(raw);
    if (!parsed || !Array.isArray(parsed.chat)) return createInitialState();
    return parsed;
  } catch {
    return createInitialState();
  }
}

function saveState(options = {}) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(serverState));
  if (!options.silent && channel) {
    channel.postMessage({ type: "snapshot", state: serverState });
  }
}

function init() {
  Object.values(devices).forEach((device) => {
    device.state = clone(serverState);
  });

  if ("BroadcastChannel" in window) {
    channel = new BroadcastChannel(CHANNEL_KEY);
    channel.onmessage = (event) => {
      if (event.data?.type !== "snapshot") return;
      if (!event.data.state || event.data.state.rev <= serverState.rev) return;
      serverState = event.data.state;
      syncOnlineDevices();
      render();
    };
  }

  window.addEventListener("storage", (event) => {
    if (event.key !== STORAGE_KEY || !event.newValue) return;
    const incoming = JSON.parse(event.newValue);
    if (incoming.rev <= serverState.rev) return;
    serverState = incoming;
    syncOnlineDevices();
    render();
  });

  bindEvents();
  render();
}

function bindEvents() {
  document.addEventListener("submit", (event) => {
    const form = event.target.closest("[data-role='composer']");
    if (!form) return;
    event.preventDefault();
    const deviceId = form.closest("[data-device]").dataset.device;
    submitCommand(deviceId);
  });

  document.addEventListener("click", (event) => {
    const globalAction = event.target.closest("[data-global-action]");
    if (globalAction) {
      handleGlobalAction(globalAction.dataset.globalAction);
      return;
    }

    const actionTarget = event.target.closest("[data-action]");
    if (!actionTarget) return;
    const root = actionTarget.closest("[data-device]");
    if (!root) return;
    const deviceId = root.dataset.device;
    const action = actionTarget.dataset.action;

    if (action === "toggle-online") toggleOnline(deviceId);
    if (action === "thread") setThread(deviceId, actionTarget.dataset.thread);
    if (action === "tab") setTab(deviceId, actionTarget.dataset.tab);
    if (action === "voice") startVoiceInput(deviceId);
    if (action === "add-note") addDocNote(deviceId);
    if (action === "rehearse") rehearse(deviceId);
    if (action === "export") exportDelivery(deviceId);
    if (action === "add-risk") addCanvasRisk(deviceId);
  });

  document.addEventListener("keydown", (event) => {
    if (!(event.metaKey || event.ctrlKey) || event.key !== "Enter") return;
    const input = event.target.closest("[data-role='commandInput']");
    if (!input) return;
    event.preventDefault();
    const deviceId = input.closest("[data-device]").dataset.device;
    submitCommand(deviceId);
  });
}

function handleGlobalAction(action) {
  if (action === "reset") {
    clearTimers();
    serverState = createInitialState();
    Object.values(devices).forEach((device) => {
      device.queue = [];
      device.online = true;
      device.activeTab = "doc";
      device.state = clone(serverState);
    });
    saveState();
    render();
    return;
  }

  if (action === "seed") {
    const command =
      "请基于本群关于智能客服升级方案的讨论，生成需求文档、自由画布和 6 页评审演示稿，并归档分享链接。";
    commitOp("desktop", createOp("USER_MESSAGE", { text: command, thread: "群聊" }, "desktop"));
    processCommand("desktop", command);
  }
}

function submitCommand(deviceId) {
  const root = getDeviceRoot(deviceId);
  const input = root.querySelector("[data-role='commandInput']");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";

  const device = devices[deviceId];
  const op = createOp("USER_MESSAGE", { text, thread: device.thread }, deviceId);
  commitOp(deviceId, op);

  if (device.online) {
    processCommand(deviceId, text);
  }
}

function processCommand(deviceId, text) {
  const parsed = planFromCommand(text);
  if (parsed.needsClarification) {
    commitSystemOp(
      createOp(
        "AGENT_CLARIFY",
        {
          question: parsed.question,
          relatedText: text,
        },
        "agent",
      ),
    );
    return;
  }

  const runId = uid("run");
  const content = buildOutputs(parsed.topic, text, parsed);
  const steps = buildStepOps(runId, parsed, content);
  const baseDelay = 160;

  commitSystemOp(createOp("AGENT_START", { runId, parsed }, "agent"));
  steps.forEach((step, index) => {
    const timer = window.setTimeout(() => {
      commitSystemOp(createOp("AGENT_STEP", step, "agent"));
    }, baseDelay + index * 560);
    timers.push(timer);
  });

  const device = devices[deviceId];
  device.activeTab = parsed.wantsDeck ? "slides" : "doc";
}

function planFromCommand(text) {
  const normalized = text.toLowerCase();
  const wantsDoc = /文档|需求|方案|prd|白板|画布|整理|沉淀/.test(normalized);
  const wantsCanvas = /画布|白板|流程|布局/.test(normalized);
  const wantsDeck = /ppt|演示|汇报|deck|排练|路演|材料/.test(normalized);
  const wantsDelivery = /交付|归档|分享|链接|导出|总结|汇报/.test(normalized);
  const hasAction = /生成|整理|输出|创建|写|做|归档|总结|排练|修改|补充/.test(normalized);

  if (!hasAction || (!wantsDoc && !wantsCanvas && !wantsDeck && !wantsDelivery)) {
    return {
      needsClarification: true,
      question: "要优先产出文档、演示稿、自由画布，还是只做讨论总结？",
    };
  }

  const topic = extractTopic(text);
  const scenes = ["A", "B"];
  if (wantsDoc || wantsCanvas || wantsDeck) scenes.push("C");
  if (wantsDeck) scenes.push("D");
  scenes.push("E");
  if (wantsDelivery || wantsDeck) scenes.push("F");

  return {
    topic,
    wantsDoc,
    wantsCanvas,
    wantsDeck,
    wantsDelivery,
    scenes: [...new Set(scenes)],
  };
}

function extractTopic(text) {
  const patterns = [
    /关于(.+?)(的讨论|的需求|的方案|，|,|生成|整理|输出|做|$)/,
    /基于(.+?)(的讨论|的需求|的方案|，|,|生成|整理|输出|做|$)/,
    /把(.+?)(整理|生成|做成|输出)/,
  ];

  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match?.[1]) return cleanTopic(match[1]);
  }

  if (text.includes("智能客服")) return "智能客服升级方案";
  if (text.includes("Agent") || text.includes("agent")) return "Agent-Pilot 协同办公助手";
  if (text.includes("办公")) return "办公协同助手";
  return cleanTopic(text).slice(0, 18) || "协同办公方案";
}

function cleanTopic(value) {
  return value
    .replace(/[。.!！?？]/g, "")
    .replace(/请|帮我|我们|这个|一下|基于本群/g, "")
    .trim();
}

function buildOutputs(topic, command, parsed) {
  const updatedAt = new Date().toISOString();
  const shortTopic = topic || "协同办公方案";
  const doc = {
    title: `${shortTopic}需求与汇报底稿`,
    updatedAt,
    blocks: [
      {
        heading: "目标",
        type: "paragraph",
        body: `围绕「${shortTopic}」建立从 IM 需求捕捉、方案沉淀、演示汇报到归档交付的闭环，让团队在同一任务上下文内完成跨端协作。`,
      },
      {
        heading: "关键用户场景",
        type: "list",
        items: [
          "在 IM 群聊中用自然语言启动任务，Agent 识别目标、约束和产出物。",
          "自动生成需求文档与自由画布，保留讨论依据、风险、决策点和行动项。",
          "把已确认内容转为演示稿，支持排练备注、页序调整和汇报归档。",
          "移动端与桌面端实时同步状态，离线编辑恢复后按操作日志合并。",
        ],
      },
      {
        heading: "实施分层",
        type: "list",
        items: [
          "IM 层：消息、语音、上下文引用和任务触发。",
          "Agent 层：Planner、工具调用、确认节点、执行状态和失败恢复。",
          "Office 层：Doc、Canvas、Slides、Delivery 四类可组合模块。",
          "Sync 层：本地队列、服务端快照、操作日志和冲突策略。",
        ],
      },
      {
        heading: "风险与确认点",
        type: "list",
        items: [
          "含糊指令需要 Agent 主动澄清，避免错误生成正式材料。",
          "跨端离线编辑不直接覆盖正文，以增量备注和时间戳合并。",
          "演示稿导出前保留人工确认，GUI 只承担精修和状态观测。",
        ],
      },
    ],
  };

  const canvas = {
    cards: [
      {
        id: uid("card"),
        type: "intent",
        title: "IM 触发",
        text: "自然语言或语音指令进入任务队列",
        x: 6,
        y: 8,
      },
      {
        id: uid("card"),
        type: "doc",
        title: "Doc / Canvas",
        text: "结构化沉淀需求、方案、风险和行动项",
        x: 38,
        y: 24,
      },
      {
        id: uid("card"),
        type: "delivery",
        title: "Slides",
        text: "提炼为评审汇报页和排练备注",
        x: 65,
        y: 48,
      },
      {
        id: uid("card"),
        type: "risk",
        title: "Sync Guard",
        text: "离线队列回放，冲突按增量合并",
        x: 18,
        y: 64,
      },
    ],
  };

  const slides = [
    {
      title: shortTopic,
      bullets: ["评审目标与业务背景", "从 IM 到成果交付的闭环", "Agent 作为主驾驶"],
      note: "开场强调当前协作成本和跨应用切换问题。",
    },
    {
      title: "核心痛点",
      bullets: ["需求散落在群聊", "文档与演示反复手工搬运", "移动端和桌面端上下文断裂"],
      note: "用一条真实讨论链路串起问题。",
    },
    {
      title: "Agent 编排",
      bullets: ["Scene A 捕捉意图", "Scene B 规划任务", "Scene C/D 生成内容", "Scene E/F 同步与交付"],
      note: "说明模块可独立演示，也可按需组合。",
    },
    {
      title: "多端一致性",
      bullets: ["操作日志驱动同步", "离线队列恢复后回放", "冲突内容增量保留"],
      note: "切换移动端离线状态演示本地补充和恢复合并。",
    },
    {
      title: "落地架构",
      bullets: ["客户端 Shell", "Agent Runtime", "Office 工具适配层", "Sync Store"],
      note: "突出工程边界和可替换平台集成。",
    },
    {
      title: "交付计划",
      bullets: ["MVP：IM + Doc + Slides", "Beta：语音与画布", "GA：平台 API 与企业权限"],
      note: "结尾给出三阶段推进和风险兜底。",
    },
  ];

  const delivery = {
    title: `${shortTopic}评审包`,
    link: `https://agent-pilot.local/share/${slugify(shortTopic)}-${Date.now().toString(36)}`,
    archiveId: `AP-${new Date().getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}`,
    summary: `已根据 IM 指令「${command}」生成文档、自由画布、演示稿与归档清单。`,
    assets: [
      { name: "需求文档", status: parsed.wantsDoc || parsed.wantsDeck ? "已生成" : "未请求" },
      { name: "自由画布", status: parsed.wantsCanvas || parsed.wantsDeck ? "已生成" : "未请求" },
      { name: "演示稿", status: parsed.wantsDeck ? "6 页" : "未请求" },
      { name: "排练备注", status: parsed.wantsDeck ? "已生成" : "未请求" },
      { name: "归档链接", status: parsed.wantsDelivery || parsed.wantsDeck ? "已创建" : "待确认" },
    ],
    updatedAt,
  };

  return { doc, canvas, slides, delivery };
}

function buildStepOps(runId, parsed, content) {
  const sceneSet = new Set(parsed.scenes);
  const ops = [
    {
      runId,
      scene: "A",
      status: "done",
      progress: 14,
      message: `已从 IM 上下文捕捉「${parsed.topic}」的任务目标。`,
      currentStep: "Scene A",
    },
    {
      runId,
      scene: "B",
      status: "done",
      progress: 30,
      message: "已拆解为可组合场景，并标记需要人工确认的交付点。",
      currentStep: "Scene B",
    },
  ];

  if (sceneSet.has("C")) {
    ops.push({
      runId,
      scene: "C",
      status: "done",
      progress: sceneSet.has("D") ? 52 : 68,
      message: "已生成需求文档和自由画布初稿。",
      currentStep: "Scene C",
      doc: content.doc,
      canvas: content.canvas,
    });
  }

  if (sceneSet.has("D")) {
    ops.push({
      runId,
      scene: "D",
      status: "done",
      progress: 72,
      message: "已生成评审演示稿和排练备注。",
      currentStep: "Scene D",
      slides: content.slides,
      rehearsal: {
        totalMinutes: 8,
        notes: ["第 1 页压缩到 45 秒", "第 4 页现场演示离线恢复", "第 6 页保留 Q&A"],
      },
    });
  }

  ops.push({
    runId,
    scene: "E",
    status: "done",
    progress: sceneSet.has("F") ? 84 : 100,
    message: "已同步到在线端，离线端将在恢复后回放队列并合并。",
    currentStep: "Scene E",
  });

  if (sceneSet.has("F")) {
    ops.push({
      runId,
      scene: "F",
      status: "done",
      progress: 100,
      message: "已生成交付归档信息和分享链接。",
      currentStep: "Scene F",
      delivery: content.delivery,
      complete: true,
    });
  }

  return ops;
}

function commitOp(deviceId, op) {
  const device = devices[deviceId];
  if (!device.online) {
    device.state = applyOp(device.state, op);
    device.queue.push(op);
    render();
    return;
  }

  serverState = applyOp(serverState, op);
  saveState();
  syncOnlineDevices();
  render();
}

function commitSystemOp(op) {
  serverState = applyOp(serverState, op);
  saveState();
  syncOnlineDevices();
  render();
}

function applyOp(state, op) {
  if (state.appliedOps?.includes(op.id)) return state;
  const next = clone(state);
  next.appliedOps = [...(next.appliedOps || []), op.id].slice(-240);
  next.rev = (next.rev || 0) + 1;
  next.updatedAt = op.at;

  if (op.type === "USER_MESSAGE") {
    next.chat.push({
      id: uid("msg"),
      author: op.deviceId === "mobile" ? "我 · 移动端" : "我 · 桌面端",
      role: "user",
      thread: op.payload.thread,
      text: op.payload.text,
      at: op.at,
    });
    next.activity.push(`IM 指令：${op.payload.text}`);
  }

  if (op.type === "AGENT_CLARIFY") {
    next.task = {
      title: "需要补充信息",
      status: "blocked",
      currentStep: "Scene B",
      progress: 18,
    };
    next.scenes.A.status = "done";
    next.scenes.B.status = "blocked";
    next.chat.push({
      id: uid("msg"),
      author: "Agent-Pilot",
      role: "agent",
      thread: "群聊",
      text: op.payload.question,
      at: op.at,
    });
  }

  if (op.type === "AGENT_START") {
    const { parsed } = op.payload;
    next.task = {
      title: parsed.topic,
      status: "running",
      currentStep: "Scene A",
      progress: 6,
    };
    next.plan = parsed.scenes.map((key) => {
      const def = SCENE_DEFS.find((scene) => scene.key === key);
      return {
        key,
        title: def.title,
        desc: def.desc,
      };
    });
    next.scenes = Object.fromEntries(
      SCENE_DEFS.map((scene) => [
        scene.key,
        {
          status: parsed.scenes.includes(scene.key) ? "pending" : "pending",
          updatedAt: op.at,
        },
      ]),
    );
    next.scenes.A.status = "running";
    next.chat.push({
      id: uid("msg"),
      author: "Agent-Pilot",
      role: "agent",
      thread: "群聊",
      text: `收到，开始编排「${parsed.topic}」。`,
      at: op.at,
    });
  }

  if (op.type === "AGENT_STEP") {
    const scene = next.scenes[op.payload.scene];
    if (scene) {
      scene.status = op.payload.status;
      scene.updatedAt = op.at;
    }

    const activeIndex = SCENE_DEFS.findIndex((item) => item.key === op.payload.scene);
    const nextScene = SCENE_DEFS[activeIndex + 1];
    if (nextScene && next.scenes[nextScene.key].status === "pending" && !op.payload.complete) {
      next.scenes[nextScene.key].status = "running";
      next.scenes[nextScene.key].updatedAt = op.at;
    }

    next.task = {
      ...next.task,
      status: op.payload.complete ? "done" : "running",
      currentStep: op.payload.currentStep,
      progress: op.payload.progress,
    };

    if (op.payload.doc) next.doc = op.payload.doc;
    if (op.payload.canvas) next.canvas = op.payload.canvas;
    if (op.payload.slides) next.slides = op.payload.slides;
    if (op.payload.rehearsal) next.rehearsal = op.payload.rehearsal;
    if (op.payload.delivery) next.delivery = op.payload.delivery;

    if (op.payload.message) {
      next.chat.push({
        id: uid("msg"),
        author: "Agent-Pilot",
        role: "agent",
        thread: "群聊",
        text: op.payload.message,
        at: op.at,
      });
      next.activity.push(op.payload.message);
    }
  }

  if (op.type === "DOC_NOTE") {
    const block = {
      heading: `协作补充 · ${op.payload.author}`,
      type: "paragraph",
      body: op.payload.text,
      at: op.at,
    };
    next.doc = {
      ...next.doc,
      title: next.doc.title === "未生成文档" ? "协作补充记录" : next.doc.title,
      updatedAt: op.at,
      blocks: [...next.doc.blocks, block],
    };
    next.chat.push({
      id: uid("msg"),
      author: "Agent-Pilot",
      role: "agent",
      thread: "群聊",
      text: `${op.payload.author} 的补充已合并到文档。`,
      at: op.at,
    });
  }

  if (op.type === "REHEARSE") {
    const notes = next.rehearsal.notes.length
      ? [...next.rehearsal.notes, op.payload.note]
      : ["开场 45 秒说明痛点", "中段演示多端同步", op.payload.note];
    next.rehearsal = {
      totalMinutes: Math.max(next.rehearsal.totalMinutes, 8),
      notes,
    };
    next.chat.push({
      id: uid("msg"),
      author: "Agent-Pilot",
      role: "agent",
      thread: "群聊",
      text: "已更新排练备注，并把当前演示控制在 8 分钟内。",
      at: op.at,
    });
  }

  if (op.type === "EXPORT") {
    next.delivery = {
      ...next.delivery,
      title: next.delivery.title === "未交付" ? `${next.task.title}交付包` : next.delivery.title,
      link:
        next.delivery.link ||
        `https://agent-pilot.local/share/${slugify(next.task.title)}-${Date.now().toString(36)}`,
      archiveId: next.delivery.archiveId || `AP-${new Date().getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}`,
      updatedAt: op.at,
      summary: next.delivery.summary || "已基于当前文档、画布和演示稿创建交付记录。",
      assets: next.delivery.assets.length
        ? next.delivery.assets
        : [
            { name: "需求文档", status: next.doc.blocks.length ? "已生成" : "空" },
            { name: "自由画布", status: next.canvas.cards.length ? "已生成" : "空" },
            { name: "演示稿", status: next.slides.length ? `${next.slides.length} 页` : "空" },
          ],
    };
    next.scenes.F.status = "done";
    next.task.progress = Math.max(next.task.progress, 100);
    next.task.status = "done";
  }

  if (op.type === "CANVAS_RISK") {
    const nextCard = {
      id: uid("card"),
      type: "risk",
      title: "新增风险",
      text: op.payload.text,
      x: 52,
      y: 12 + ((next.canvas.cards.length * 13) % 68),
    };
    next.canvas = {
      cards: [...next.canvas.cards, nextCard],
    };
  }

  return next;
}

function toggleOnline(deviceId) {
  const device = devices[deviceId];
  device.online = !device.online;

  if (device.online) {
    const queued = [...device.queue];
    device.queue = [];
    queued.forEach((op) => {
      serverState = applyOp(serverState, op);
    });
    saveState();
    syncOnlineDevices();
    render();

    queued
      .filter((op) => op.type === "USER_MESSAGE")
      .forEach((op, index) => {
        const timer = window.setTimeout(() => processCommand(deviceId, op.payload.text), index * 260);
        timers.push(timer);
      });
    return;
  }

  device.state = clone(serverState);
  render();
}

function setThread(deviceId, thread) {
  devices[deviceId].thread = thread;
  render();
}

function setTab(deviceId, tab) {
  devices[deviceId].activeTab = tab;
  render();
}

function addDocNote(deviceId) {
  const root = getDeviceRoot(deviceId);
  const input = root.querySelector("[data-role='docNote']");
  const text = input?.value.trim();
  if (!text) return;
  input.value = "";
  commitOp(
    deviceId,
    createOp(
      "DOC_NOTE",
      {
        text,
        author: devices[deviceId].label,
      },
      deviceId,
    ),
  );
}

function rehearse(deviceId) {
  commitOp(
    deviceId,
    createOp(
      "REHEARSE",
      {
        note: `${devices[deviceId].label} 标记：现场演示后预留 60 秒回应评委问题。`,
      },
      deviceId,
    ),
  );
  devices[deviceId].activeTab = "slides";
}

function exportDelivery(deviceId) {
  commitOp(deviceId, createOp("EXPORT", {}, deviceId));
  devices[deviceId].activeTab = "delivery";
}

function addCanvasRisk(deviceId) {
  commitOp(
    deviceId,
    createOp(
      "CANVAS_RISK",
      {
        text: `${devices[deviceId].label} 补充：外部平台 API 限流时需要降级到本地草稿。`,
      },
      deviceId,
    ),
  );
  devices[deviceId].activeTab = "canvas";
}

function startVoiceInput(deviceId) {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const root = getDeviceRoot(deviceId);
  const input = root.querySelector("[data-role='commandInput']");

  if (!Recognition) {
    input.value = "请生成需求文档和评审演示稿，并归档分享链接。";
    input.focus();
    return;
  }

  const recognition = new Recognition();
  recognition.lang = "zh-CN";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  recognition.onresult = (event) => {
    input.value = event.results[0][0].transcript;
    input.focus();
  };
  recognition.start();
}

function syncOnlineDevices() {
  Object.values(devices).forEach((device) => {
    if (device.online) {
      device.state = clone(serverState);
    }
  });
}

function render() {
  document.getElementById("serverStatus").textContent = `Server rev ${serverState.rev} · ${formatTime(
    serverState.updatedAt,
  )}`;

  Object.entries(devices).forEach(([deviceId, device]) => {
    const root = getDeviceRoot(deviceId);
    renderDeviceStatus(root, device);
    renderThread(root, device);
    renderChat(root, device.state);
    renderPlanner(root, device);
    renderTabs(root, deviceId, device);
    renderWorkspace(root, deviceId, device);
  });
}

function renderDeviceStatus(root, device) {
  const sync = root.querySelector("[data-role='sync']");
  sync.className = `sync-pill ${device.online ? "online" : "offline"}`;
  const queueText = device.queue.length ? ` · 队列 ${device.queue.length}` : "";
  sync.textContent = device.online ? `在线 rev ${device.state.rev}` : `离线${queueText}`;
}

function renderThread(root, device) {
  root.querySelectorAll("[data-action='thread']").forEach((button) => {
    button.classList.toggle("active", button.dataset.thread === device.thread);
  });
}

function renderChat(root, state) {
  const chat = root.querySelector("[data-role='chat']");
  chat.innerHTML = state.chat
    .slice(-16)
    .map(
      (message) => `
        <article class="message ${message.role}">
          <div class="message-meta">${escapeHtml(message.author)} · ${escapeHtml(message.thread)} · ${formatTime(
            message.at,
          )}</div>
          <div class="message-bubble">${escapeHtml(message.text)}</div>
        </article>
      `,
    )
    .join("");
  chat.scrollTop = chat.scrollHeight;
}

function renderPlanner(root, device) {
  const state = device.state;
  root.querySelector("[data-role='progressText']").textContent = `${state.task.statusLabel || statusText(
    state.task.status,
  )} · ${state.task.progress}%`;
  root.querySelector("[data-role='progressFill']").style.width = `${state.task.progress}%`;

  const sceneList = root.querySelector("[data-role='scenes']");
  sceneList.innerHTML = SCENE_DEFS.map((scene, index) => {
    const value = state.scenes[scene.key] || { status: "pending" };
    return `
      <article class="scene-item">
        <div class="scene-index">${index + 1}</div>
        <div>
          <div class="scene-title">${scene.key}. ${escapeHtml(scene.title)}</div>
          <div class="scene-desc">${escapeHtml(scene.desc)}</div>
        </div>
        <span class="status-badge ${value.status}">${statusText(value.status)}</span>
      </article>
    `;
  }).join("");

  const queue = root.querySelector("[data-role='queue']");
  queue.textContent = device.online
    ? `当前步骤：${state.task.currentStep} · ${state.task.title}`
    : `本端离线编辑会进入本地队列，恢复在线后回放合并。待同步 ${device.queue.length} 条。`;
}

function renderTabs(root, deviceId, device) {
  const tabs = root.querySelector("[data-role='tabs']");
  tabs.innerHTML = TABS.map(
    (tab) => `
      <button type="button" data-action="tab" data-tab="${tab.key}" class="${device.activeTab === tab.key ? "active" : ""}">
        ${tab.label}
      </button>
    `,
  ).join("");
}

function renderWorkspace(root, deviceId, device) {
  const state = device.state;
  const body = root.querySelector("[data-role='workspace']");
  if (device.activeTab === "doc") body.innerHTML = renderDoc(state, deviceId);
  if (device.activeTab === "canvas") body.innerHTML = renderCanvas(state);
  if (device.activeTab === "slides") body.innerHTML = renderSlides(state);
  if (device.activeTab === "delivery") body.innerHTML = renderDelivery(state);
}

function renderDoc(state, deviceId) {
  const blocks = state.doc.blocks.length
    ? state.doc.blocks
        .map((block) => {
          const content =
            block.type === "list"
              ? `<ul>${block.items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
              : `<p>${escapeHtml(block.body)}</p>`;
          return `
            <section class="doc-block">
              <h4>${escapeHtml(block.heading)}</h4>
              ${content}
            </section>
          `;
        })
        .join("")
    : `<div class="empty-state">等待 Agent 生成文档</div>`;

  return `
    <div class="doc-view">
      <div class="doc-title">
        <h3>${escapeHtml(state.doc.title)}</h3>
        <span>更新于 ${formatTime(state.doc.updatedAt)} · ${state.doc.blocks.length} 个内容块</span>
      </div>
      ${blocks}
      <div class="note-composer">
        <textarea class="doc-note-input" data-role="docNote" rows="2" placeholder="补充文档内容"></textarea>
        <div class="note-actions">
          <button type="button" class="small-btn" data-action="add-risk">添加风险卡</button>
          <button type="button" class="small-btn" data-action="add-note">合并补充</button>
          <button type="button" class="small-btn" data-action="export">归档</button>
        </div>
      </div>
    </div>
  `;
}

function renderCanvas(state) {
  if (!state.canvas.cards.length) {
    return `<div class="empty-state">等待 Agent 生成自由画布</div>`;
  }

  return `
    <div class="canvas-board">
      ${state.canvas.cards
        .map(
          (card) => `
            <article class="canvas-card ${card.type}" style="left:${card.x}%;top:${card.y}%">
              <h4>${escapeHtml(card.title)}</h4>
              <p>${escapeHtml(card.text)}</p>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderSlides(state) {
  if (!state.slides.length) {
    return `<div class="empty-state">等待 Agent 生成演示稿</div>`;
  }

  return `
    <div class="doc-view">
      <div class="note-actions">
        <button type="button" class="small-btn" data-action="rehearse">排练</button>
        <button type="button" class="small-btn" data-action="export">归档</button>
      </div>
      <div class="slide-grid">
        ${state.slides
          .map(
            (slide, index) => `
              <article class="slide-card">
                <div class="slide-top">Slide ${index + 1}</div>
                <h3>${escapeHtml(slide.title)}</h3>
                <ul>${slide.bullets.map((bullet) => `<li>${escapeHtml(bullet)}</li>`).join("")}</ul>
                <div class="slide-note">${escapeHtml(slide.note)}</div>
              </article>
            `,
          )
          .join("")}
      </div>
      <section class="doc-block">
        <h4>排练备注 · ${state.rehearsal.totalMinutes || 0} 分钟</h4>
        ${
          state.rehearsal.notes.length
            ? `<ul>${state.rehearsal.notes.map((note) => `<li>${escapeHtml(note)}</li>`).join("")}</ul>`
            : "<p>暂无排练备注</p>"
        }
      </section>
    </div>
  `;
}

function renderDelivery(state) {
  const hasDelivery = Boolean(state.delivery.link || state.delivery.assets.length);
  if (!hasDelivery) {
    return `
      <div class="doc-view">
        <div class="empty-state">等待 Agent 生成交付归档</div>
        <div class="note-actions">
          <button type="button" class="small-btn" data-action="export">归档</button>
        </div>
      </div>
    `;
  }

  return `
    <div class="delivery-view">
      <section class="delivery-hero">
        <h3>${escapeHtml(state.delivery.title)}</h3>
        <div class="delivery-meta">${escapeHtml(state.delivery.summary)}</div>
        <span class="delivery-link">${escapeHtml(state.delivery.link)}</span>
        <div class="delivery-meta">Archive ID ${escapeHtml(state.delivery.archiveId)} · ${formatTime(state.delivery.updatedAt)}</div>
      </section>
      <ul class="delivery-list">
        ${state.delivery.assets
          .map(
            (asset) => `
              <li>
                <strong>${escapeHtml(asset.name)}</strong>
                <span>${escapeHtml(asset.status)}</span>
              </li>
            `,
          )
          .join("")}
      </ul>
    </div>
  `;
}

function createOp(type, payload, deviceId) {
  return {
    id: uid("op"),
    type,
    payload,
    at: new Date().toISOString(),
    deviceId: deviceId || currentDeviceFromType(type),
  };
}

function currentDeviceFromType(type) {
  return type.startsWith("AGENT") ? "agent" : "desktop";
}

function uid(prefix) {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatTime(value) {
  if (!value) return "--:--";
  const date = new Date(value);
  return date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function statusText(status) {
  const map = {
    idle: "待命",
    pending: "待执行",
    running: "执行中",
    done: "完成",
    blocked: "待澄清",
  };
  return map[status] || status;
}

function slugify(value) {
  return encodeURIComponent(String(value).trim().replace(/\s+/g, "-").toLowerCase());
}

function getDeviceRoot(deviceId) {
  return document.querySelector(`[data-device='${deviceId}']`);
}

function clearTimers() {
  timers.forEach((timer) => window.clearTimeout(timer));
  timers = [];
}

init();
