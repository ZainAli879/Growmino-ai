const { useEffect, useMemo, useState } = React;

const DAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday"
];

const CONTENT_TYPES = [
  "Educational",
  "Educational Carousel Post",
  "Educational Post + Infographic",
  "Pain-point",
  "Case Study",
  "Case Study Post",
  "Industry Insight",
  "Founder Authority",
  "Authority Post (Tips Post)",
  "Automation Tip",
  "Client Testimonial",
  "Testimonial Post"
];

const CONTENT_TYPES_BY_DAY = {
  Monday: ["Educational", "Educational Carousel Post", "Educational Post + Infographic"],
  Tuesday: ["Pain-point"],
  Wednesday: ["Case Study", "Case Study Post"],
  Thursday: ["Industry Insight"],
  Friday: ["Founder Authority", "Authority Post (Tips Post)"],
  Saturday: ["Automation Tip"],
  Sunday: ["Client Testimonial", "Testimonial Post"]
};

const PLATFORMS = ["linkedin", "instagram", "facebook"];
const PUBLISHABLE_PLATFORMS = ["facebook", "instagram"];
const STEPS = ["Brief", "Plan", "Generate", "Review", "Publish", "Posts"];

const SIDEBAR_ITEMS = [
  "Create Post",
  "Generated Posts",
  "Weekly Posts",
  "Content Calendar",
  "Drafts",
  "Published Posts",
  "Brand Settings",
  "Integrations"
];

const PRESETS = {
  None: {
    business_name: "",
    industry: "",
    offer: "",
    target_audience: "",
    audience_pain_points: "",
    weekly_focus_topic: "",
    day: "Monday",
    content_type: "Educational",
    tone: "",
    brand_personality: "",
    proof_assets: "",
    company_logo_url: "",
    platform: "linkedin"
  },
  "LinkedIn B2B": {
    business_name: "FlowOps Studio",
    industry: "B2B Automation",
    offer: "Workflow automation sprints",
    target_audience: "Operations managers at SMBs",
    audience_pain_points: "Manual follow-ups and inconsistent handoffs",
    weekly_focus_topic: "Reducing lead handoff bottlenecks",
    day: "Monday",
    content_type: "Educational",
    tone: "Practical and confident",
    brand_personality: "Direct, modern, helpful",
    proof_assets: "",
    company_logo_url: "",
    platform: "linkedin"
  },
  "GrowMino AI": {
    business_name: "GrowMino AI",
    industry: "AI content generation and social media automation",
    offer: "AI-powered captions, post visuals, and content workflow automation for growing businesses",
    target_audience: "founders, agencies, local businesses, and small teams that need consistent social media content",
    audience_pain_points: "Struggling to post consistently, spending too much time writing captions, needing better visuals, and lacking a repeatable content system",
    weekly_focus_topic: "Turning one business brief into platform-ready social posts with captions and visuals",
    day: "Monday",
    content_type: "Educational",
    tone: "Confident, helpful, and practical",
    brand_personality: "Modern, sharp, reliable, and growth-focused",
    proof_assets: "GrowMino AI helps businesses create ready-to-post captions and visuals from one simple brief, reducing manual content planning and design time.",
    company_logo_url: "",
    platform: "linkedin"
  },
  "Instagram D2C": {
    business_name: "UrbanWear Boutique",
    industry: "Fashion Retail",
    offer: "Trend-led streetwear with same-day dispatch",
    target_audience: "Gen Z and young millennials",
    audience_pain_points: "Late deliveries and wrong sizes",
    weekly_focus_topic: "How to speed up order fulfillment",
    day: "Saturday",
    content_type: "Automation Tip",
    tone: "Energetic and relatable",
    brand_personality: "Playful, fast, customer-first",
    proof_assets: "",
    company_logo_url: "",
    platform: "instagram"
  },
  "Facebook Local Service": {
    business_name: "BrightHome Repairs",
    industry: "Home Services",
    offer: "Same-week maintenance visits",
    target_audience: "Homeowners in the city",
    audience_pain_points: "No-shows and unclear service timelines",
    weekly_focus_topic: "Reliable booking and service updates",
    day: "Thursday",
    content_type: "Industry Insight",
    tone: "Friendly and reassuring",
    brand_personality: "Helpful, honest, reliable",
    proof_assets: "",
    company_logo_url: "",
    platform: "facebook"
  }
};

const INITIAL_FORM = { ...PRESETS.None };
const API_BASE_URL = "http://127.0.0.1:8000";

function absoluteUrl(path) {
  if (!path) {
    return "";
  }
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

function titleCase(value) {
  return value
    .split(/[\s_-]+/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function buildPostPreview(platform, caption, headline) {
  if (platform === "instagram") {
    return {
      network: "Instagram",
      page: "growmino.agency",
      timestamp: "Just now",
      body: caption || "Your Instagram caption will appear here.",
      headline: headline || "Visual-led social post"
    };
  }

  if (platform === "linkedin") {
    return {
      network: "LinkedIn",
      page: "GrowMino Publisher",
      timestamp: "Today",
      body: caption || "Your LinkedIn post will appear here.",
      headline: headline || "Professional thought leadership"
    };
  }

  return {
    network: "Facebook",
    page: "GrowMino Publisher",
    timestamp: "Today",
    body: caption || "Your Facebook post will appear here.",
    headline: headline || "Social post preview"
  };
}

function App() {
  const [preset, setPreset] = useState("None");
  const [form, setForm] = useState(INITIAL_FORM);
  const [activeStep, setActiveStep] = useState("Brief");
  const [generationMode, setGenerationMode] = useState("both");
  const [generateState, setGenerateState] = useState({ loading: false, error: "", result: null });
  const [publishState, setPublishState] = useState({ loading: false, error: "", success: "" });
  const [publishMode, setPublishMode] = useState("now");
  const [scheduledFor, setScheduledFor] = useState("");
  const [toast, setToast] = useState({ message: "", type: "" });
  const [publishSuccess, setPublishSuccess] = useState(null);
  const [generatedPostsState, setGeneratedPostsState] = useState({ loading: false, error: "", posts: [] });
  const [weeklyCarouselPage, setWeeklyCarouselPage] = useState(0);
  const [weeklyPostFilters, setWeeklyPostFilters] = useState({
    date_from: "",
    date_to: "",
    platform: "all",
    day: "all"
  });
  const [weeklyPlanForm, setWeeklyPlanForm] = useState({
    week_start_date: "",
    weekly_goal: "Create a focused week of content that educates prospects and drives qualified conversations",
    theme: "AI-powered social content and lead generation workflows",
    posts_count: 5,
    platforms: ["linkedin"]
  });
  const [contentPlanState, setContentPlanState] = useState({ loading: false, error: "", plan: null });
  const [imagePreview, setImagePreview] = useState(null);
  const sectionRefs = {
    Brief: React.useRef(null),
    Plan: React.useRef(null),
    Generate: React.useRef(null),
    Review: React.useRef(null),
    Publish: React.useRef(null),
    Posts: React.useRef(null),
    WeeklyPosts: React.useRef(null)
  };
  const generatedPostsCarouselRef = React.useRef(null);
  const weeklyPostsCarouselRef = React.useRef(null);
  const [publishForm, setPublishForm] = useState({
    platform: "facebook",
    caption: "",
    image_url: "",
    uploadedFile: null,
    facebook_page_id: "",
    access_token: "",
    facebook_access_token: "",
    instagram_business_account_id: "",
    instagram_access_token: ""
  });
  const [uploadedPreview, setUploadedPreview] = useState("");

  useEffect(() => {
    if (!publishForm.uploadedFile) {
      setUploadedPreview("");
      return undefined;
    }
    const preview = URL.createObjectURL(publishForm.uploadedFile);
    setUploadedPreview(preview);
    return () => URL.revokeObjectURL(preview);
  }, [publishForm.uploadedFile]);

  useEffect(() => {
    if (!toast.message) {
      return undefined;
    }
    const timeout = window.setTimeout(() => setToast({ message: "", type: "" }), 2400);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  useEffect(() => {
    if ((activeStep === "Posts" || activeStep === "WeeklyPosts") && !generatedPostsState.posts.length && !generatedPostsState.loading) {
      loadGeneratedPosts();
    }
  }, [activeStep]);

  const generatedImage = generateState.result?.openai_image || null;
  const generatedPreviewUrl = generatedImage?.public_url ? absoluteUrl(generatedImage.public_url) : "";
  const previewData = buildPostPreview(
    publishForm.platform,
    publishForm.caption || generateState.result?.caption || "",
    generateState.result?.headline || ""
  );
  const currentStepIndex = STEPS.indexOf(activeStep);
  const stepProgress = currentStepIndex >= 0 ? ((currentStepIndex + 1) / STEPS.length) * 100 : 0;
  const activePlatformLabel = titleCase(publishForm.platform);
  const publishModeLabel = publishMode === "now" ? "Publish now" : publishMode === "schedule" ? "Schedule for later" : "Save as draft";

  const activePreviewUrl = useMemo(() => {
    if (uploadedPreview) {
      return uploadedPreview;
    }
    if (publishForm.image_url) {
      return publishForm.image_url;
    }
    return generatedPreviewUrl;
  }, [generatedPreviewUrl, publishForm.image_url, uploadedPreview]);
  const logoPreviewUrl = form.company_logo_url?.startsWith("data:image") || form.company_logo_url?.startsWith("http")
    ? form.company_logo_url
    : "";
  const validContentTypes = CONTENT_TYPES_BY_DAY[form.day] || CONTENT_TYPES;
  const weeklyGalleryPosts = useMemo(() => {
    return generatedPostsState.posts.filter((post) => {
      const createdDate = post.created_at ? String(post.created_at).slice(0, 10) : "";
      if (weeklyPostFilters.date_from && createdDate && createdDate < weeklyPostFilters.date_from) {
        return false;
      }
      if (weeklyPostFilters.date_to && createdDate && createdDate > weeklyPostFilters.date_to) {
        return false;
      }
      if (weeklyPostFilters.platform !== "all" && post.platform !== weeklyPostFilters.platform) {
        return false;
      }
      if (weeklyPostFilters.day !== "all" && post.day !== weeklyPostFilters.day) {
        return false;
      }
      return true;
    });
  }, [generatedPostsState.posts, weeklyPostFilters]);
  const weeklyCarouselPageCount = Math.max(1, Math.ceil(weeklyGalleryPosts.length / 2));
  const visibleWeeklyStart = weeklyGalleryPosts.length ? weeklyCarouselPage * 2 + 1 : 0;
  const visibleWeeklyEnd = Math.min(weeklyGalleryPosts.length, visibleWeeklyStart + 1);

  useEffect(() => {
    setWeeklyCarouselPage(0);
    if (weeklyPostsCarouselRef.current) {
      weeklyPostsCarouselRef.current.scrollTo({ left: 0 });
    }
  }, [weeklyGalleryPosts.length, weeklyPostFilters]);

  function updateForm(field, value) {
    setForm((current) => {
      if (field === "day") {
        const nextTypes = CONTENT_TYPES_BY_DAY[value] || CONTENT_TYPES;
        return {
          ...current,
          day: value,
          content_type: nextTypes.includes(current.content_type) ? current.content_type : nextTypes[0]
        };
      }
      return { ...current, [field]: value };
    });
  }

  function handleLogoUpload(event) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    if (!file.type.startsWith("image/")) {
      triggerToast("Please choose an image logo file", "error");
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      updateForm("company_logo_url", String(reader.result || ""));
      triggerToast("Logo added to brief", "success");
    };
    reader.onerror = () => triggerToast("Could not read logo file", "error");
    reader.readAsDataURL(file);
  }

  function updatePublishForm(field, value) {
    setPublishForm((current) => ({ ...current, [field]: value }));
  }

  function updateWeeklyPlanForm(field, value) {
    setWeeklyPlanForm((current) => ({ ...current, [field]: value }));
  }

  function toggleWeeklyPlanPlatform(platform) {
    setWeeklyPlanForm((current) => {
      const exists = current.platforms.includes(platform);
      const nextPlatforms = exists
        ? current.platforms.filter((item) => item !== platform)
        : [...current.platforms, platform];
      return {
        ...current,
        platforms: nextPlatforms.length ? nextPlatforms : [platform]
      };
    });
  }

  function triggerToast(message, type = "success") {
    setToast({ message, type });
  }

  function focusSection(step) {
    setActiveStep(step);
    window.requestAnimationFrame(() => {
      sectionRefs[step]?.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  function handleSidebarItem(item) {
    if (item === "Create Post") {
      focusSection("Brief");
      return;
    }
    if (item === "Generated Posts") {
      focusSection("Posts");
      loadGeneratedPosts();
      return;
    }
    if (item === "Weekly Posts") {
      focusSection("WeeklyPosts");
      loadGeneratedPosts();
      return;
    }
    if (item === "Content Calendar") {
      focusSection("Plan");
      return;
    }
    if (item === "Drafts") {
      triggerToast(`${item} coming soon`, "success");
      return;
    }
    if (item === "Published Posts") {
      focusSection("Review");
      return;
    }
    if (item === "Brand Settings") {
      focusSection("Brief");
      return;
    }
    if (item === "Integrations") {
      focusSection("Publish");
      return;
    }
  }

  async function loadGeneratedPosts() {
    setGeneratedPostsState((current) => ({ ...current, loading: true, error: "" }));
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/posts?limit=50`);
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(payload?.detail || "Could not load generated posts.");
      }
      setGeneratedPostsState({ loading: false, error: "", posts: payload?.posts || [] });
    } catch (error) {
      setGeneratedPostsState({ loading: false, error: error.message, posts: [] });
      triggerToast("Could not load generated posts", "error");
    }
  }

  function useGeneratedPost(post) {
    const platform = PUBLISHABLE_PLATFORMS.includes(post.platform) ? post.platform : "facebook";
    setGenerateState({
      loading: false,
      error: "",
      result: {
        post_id: post.id,
        caption: post.caption,
        headline: post.headline,
        meta: {
          platform: post.platform,
          day: post.day,
          content_type: post.content_type,
          business_name: form.business_name
        },
        openai_image: {
          public_url: post.image_url,
          file_path: post.image_file_path,
          alt_text: post.alt_text
        }
      }
    });
    setPublishForm((current) => ({
      ...current,
      platform,
      caption: post.caption,
      image_url: post.image_url,
      uploadedFile: null
    }));
    focusSection("Review");
    triggerToast("Loaded generated post", "success");
  }

  function scrollCarousel(carouselRef, direction) {
    const carousel = carouselRef.current;
    if (!carousel) {
      return;
    }
    const amount = carousel.clientWidth;
    carousel.scrollBy({
      left: direction === "next" ? amount : -amount,
      behavior: "smooth"
    });
  }

  function goToWeeklyCarouselPage(page) {
    const carousel = weeklyPostsCarouselRef.current;
    const nextPage = Math.max(0, Math.min(page, weeklyCarouselPageCount - 1));
    setWeeklyCarouselPage(nextPage);
    if (carousel) {
      carousel.scrollTo({
        left: carousel.clientWidth * nextPage,
        behavior: "smooth"
      });
    }
  }

  function scrollWeeklyCarousel(direction) {
    goToWeeklyCarouselPage(weeklyCarouselPage + (direction === "next" ? 1 : -1));
  }

  function syncWeeklyCarouselPage() {
    const carousel = weeklyPostsCarouselRef.current;
    if (!carousel || !carousel.clientWidth) {
      return;
    }
    const nextPage = Math.round(carousel.scrollLeft / carousel.clientWidth);
    setWeeklyCarouselPage(Math.max(0, Math.min(nextPage, weeklyCarouselPageCount - 1)));
  }

  function applyPreset(nextPreset) {
    setPreset(nextPreset);
    setForm({ ...PRESETS[nextPreset] });
    triggerToast(`${nextPreset} preset loaded`, "success");
  }

  async function createPostFromPayload(payload, mode = "both") {
    setGenerationMode(mode);
    setActiveStep("Generate");
    setGenerateState({ loading: true, error: "", result: null });
    setPublishState({ loading: false, error: "", success: "" });
    setPublishSuccess(null);

    const response = await fetch(`${API_BASE_URL}/api/v1/posts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const body = await response.json().catch(() => null);

    if (!response.ok) {
      throw new Error(body?.detail || "Generation failed.");
    }

    setGenerateState({ loading: false, error: "", result: body });
    loadGeneratedPosts();
    setPublishForm((current) => ({
      ...current,
      platform: PUBLISHABLE_PLATFORMS.includes(body?.meta?.platform) ? body.meta.platform : "facebook",
      caption: body?.caption || current.caption,
      image_url: "",
      uploadedFile: null
    }));
    triggerToast("Content generated", "success");
    return body;
  }

  async function handleGenerate(event, mode = "both") {
    event.preventDefault();
    try {
      await createPostFromPayload(form, mode);
    } catch (error) {
      setGenerateState({ loading: false, error: error.message, result: null });
      triggerToast("Generation failed", "error");
    }
  }

  async function handleCreateWeeklyPlan(event) {
    event.preventDefault();
    setActiveStep("Plan");
    setContentPlanState({ loading: true, error: "", plan: null });

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/content-plans`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          business_name: form.business_name,
          industry: form.industry,
          offer: form.offer,
          target_audience: form.target_audience,
          audience_pain_points: form.audience_pain_points,
          tone: form.tone,
          brand_personality: form.brand_personality,
          cta_preference: form.cta_preference,
          proof_assets: form.proof_assets,
          company_logo_url: form.company_logo_url,
          week_start_date: weeklyPlanForm.week_start_date,
          weekly_goal: weeklyPlanForm.weekly_goal,
          theme: weeklyPlanForm.theme,
          platforms: weeklyPlanForm.platforms,
          posts_count: Number(weeklyPlanForm.posts_count) || 5
        })
      });
      const payload = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(payload?.detail || "Could not create weekly plan.");
      }

      setContentPlanState({ loading: false, error: "", plan: payload });
      loadGeneratedPosts();
      triggerToast("Weekly posts generated", "success");
    } catch (error) {
      setContentPlanState({ loading: false, error: error.message, plan: null });
      triggerToast("Plan generation failed", "error");
    }
  }

  async function generatePlanItem(item) {
    const nextPayload = {
      ...form,
      weekly_focus_topic: `${item.topic}. Angle: ${item.angle}. Hook direction: ${item.hook_direction}. Visual direction: ${item.visual_direction}`,
      day: item.day,
      content_type: item.content_type,
      platform: item.platform,
      cta_preference: item.cta_direction || form.cta_preference
    };
    setForm(nextPayload);
    try {
      await createPostFromPayload(nextPayload, "both");
    } catch (error) {
      setGenerateState({ loading: false, error: error.message, result: null });
      triggerToast("Generation failed", "error");
    }
  }

  async function uploadImageIfNeeded() {
    if (!publishForm.uploadedFile) {
      return { file_path: generatedImage?.file_path || "", public_url: generatedPreviewUrl };
    }

    const dataUrl = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(new Error("Could not read uploaded image."));
      reader.readAsDataURL(publishForm.uploadedFile);
    });

    const response = await fetch(`${API_BASE_URL}/api/v1/assets`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        file_name: publishForm.uploadedFile.name,
        data_url: dataUrl
      })
    });
    const payload = await response.json().catch(() => null);

    if (!response.ok) {
      throw new Error(payload?.detail || "Image upload failed.");
    }

    return payload;
  }

  async function handlePublish(event) {
    event.preventDefault();
    setPublishState({ loading: true, error: "", success: "" });
    setPublishSuccess(null);

    try {
      const uploaded = await uploadImageIfNeeded();
      const response = await fetch(`${API_BASE_URL}/api/v1/publishing-jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          platform: publishForm.platform,
          caption: publishForm.caption,
          image_url: publishForm.image_url,
          image_file_path: publishForm.image_url ? "" : uploaded.file_path,
          access_token: publishForm.access_token,
          facebook_page_id: publishForm.facebook_page_id,
          facebook_access_token: publishForm.facebook_access_token,
          instagram_business_account_id: publishForm.instagram_business_account_id,
          instagram_access_token: publishForm.instagram_access_token
        })
      });
      const payload = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(payload?.detail || "Publishing failed.");
      }

      const publishedMessage = payload?.message || "Published successfully.";
      setPublishState({ loading: false, error: "", success: publishedMessage });
      setPublishSuccess({
        platform: activePlatformLabel,
        time: new Date().toLocaleString(),
        message: publishedMessage
      });
      triggerToast("Post published", "success");
    } catch (error) {
      setPublishState({ loading: false, error: error.message, success: "" });
      triggerToast("Publish failed", "error");
    }
  }

  return (
    <div className="app-shell">
      <div className="dashboard-shell">
        <aside className="sidebar">
          <div className="brand-block">
            <div className="brand-mark">GM</div>
            <div>
              <strong>GrowMino Publisher</strong>
              <span>AI content dashboard</span>
            </div>
          </div>

          <div className="workspace-switcher">
            <span className="mini-label">Workspace</span>
            <strong>GrowMino Studio</strong>
            <p>Premium content generation and publishing</p>
          </div>

          <nav className="sidebar-nav">
            {SIDEBAR_ITEMS.map((item) => (
              <button
                key={item}
                type="button"
                className={
                  (item === "Create Post" && activeStep === "Brief") ||
                  (item === "Generated Posts" && activeStep === "Posts") ||
                  (item === "Weekly Posts" && activeStep === "WeeklyPosts") ||
                  (item === "Content Calendar" && activeStep === "Plan") ||
                  (item === "Integrations" && activeStep === "Publish")
                    ? "sidebar-item active"
                    : "sidebar-item"
                }
                onClick={() => handleSidebarItem(item)}
              >
                {item}
              </button>
            ))}
          </nav>
        </aside>

        <div className="workspace-shell">
          <header className="topbar">
            <div>
              <span className="eyebrow">GrowMino Publisher</span>
              <h1>Create Social Post</h1>
              <p>Generate, review, and publish platform-ready content.</p>
            </div>

            <div className="topbar-actions">
              <button type="button" className="ghost-button" onClick={() => triggerToast("Draft saved", "success")}>Save Draft</button>
              <button type="button" className="ghost-button" onClick={() => setActiveStep("Review")}>Preview</button>
              <div className="avatar">GM</div>
            </div>
          </header>

          <section className="stepper-card">
            <div className="stepper-track">
              {STEPS.map((step, index) => {
                const stepIndex = index + 1;
                const active = step === activeStep;
                const complete = index < currentStepIndex;
                return (
                  <button key={step} type="button" className={active ? "stepper-step active" : complete ? "stepper-step complete" : "stepper-step"} onClick={() => {
                    setActiveStep(step);
                    if (step === "Posts") {
                      loadGeneratedPosts();
                    }
                  }}>
                    <span>{stepIndex}</span>
                    {step}
                  </button>
                );
              })}
            </div>
            <div className="stepper-meter">
              <span style={{ width: `${stepProgress}%` }} />
            </div>
          </section>

          <main className="dashboard-grid">
            <section className="main-column">
              <div ref={sectionRefs.Brief} className={activeStep === "Brief" ? "workflow-panel active" : "workflow-panel"}>
                  <div className="panel-head">
                  <div className="panel-title-row">
                    <div>
                      <h2>Brief</h2>
                      <p>Organize the business context into clean cards instead of one long form.</p>
                    </div>
                    <span className="status-pill">Setup</span>
                  </div>
                </div>

                <div className="brief-toolbar">
                  <label className="field field-full">
                    <span>Quick presets</span>
                    <select value={preset} onChange={(event) => applyPreset(event.target.value)}>
                      <option value="None">Choose a preset</option>
                      {Object.keys(PRESETS)
                        .filter((item) => item !== "None")
                        .map((item) => (
                          <option key={item} value={item}>
                            {item}
                          </option>
                        ))}
                    </select>
                  </label>
                </div>

                <form className="workflow-form">
                  <section className="card-section">
                    <div className="section-head">
                      <h3>Business Profile</h3>
                      <p>Core business details for the model.</p>
                    </div>
                    <div className="form-grid">
                      <label className="field">
                        <span>Business name</span>
                        <input value={form.business_name} onChange={(event) => updateForm("business_name", event.target.value)} placeholder="GrowMino" />
                      </label>
                      <label className="field">
                        <span>Industry</span>
                        <input value={form.industry} onChange={(event) => updateForm("industry", event.target.value)} placeholder="AI automation agency" />
                      </label>
                      <label className="field">
                        <span>Offer</span>
                        <input value={form.offer} onChange={(event) => updateForm("offer", event.target.value)} placeholder="Done-for-you AI systems" />
                      </label>
                      <label className="field">
                        <span>Target audience</span>
                        <input value={form.target_audience} onChange={(event) => updateForm("target_audience", event.target.value)} placeholder="Founders and local businesses" />
                      </label>
                    </div>
                  </section>

                  <section className="card-section">
                    <div className="section-head">
                      <h3>Content Strategy</h3>
                      <p>Voice, format, and topical direction.</p>
                    </div>
                    <div className="form-grid">
                      <label className="field field-full">
                        <span>Audience pain points</span>
                        <textarea value={form.audience_pain_points} onChange={(event) => updateForm("audience_pain_points", event.target.value)} rows="3" placeholder="Slow response times, missed leads, repetitive admin work" />
                      </label>
                      <label className="field field-full">
                        <span>Weekly focus topic</span>
                        <input value={form.weekly_focus_topic} onChange={(event) => updateForm("weekly_focus_topic", event.target.value)} placeholder="How automation helps businesses respond faster" />
                      </label>
                      <label className="field">
                        <span>Day</span>
                        <select value={form.day} onChange={(event) => updateForm("day", event.target.value)}>
                          {DAYS.map((item) => (
                            <option key={item} value={item}>
                              {item}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="field">
                        <span>Content type</span>
                        <select value={form.content_type} onChange={(event) => updateForm("content_type", event.target.value)}>
                          {validContentTypes.map((item) => (
                            <option key={item} value={item}>
                              {item}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="field">
                        <span>Platform</span>
                        <select value={form.platform} onChange={(event) => updateForm("platform", event.target.value)}>
                          {PLATFORMS.map((item) => (
                            <option key={item} value={item}>
                              {item}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="field">
                        <span>Tone</span>
                        <input value={form.tone} onChange={(event) => updateForm("tone", event.target.value)} placeholder="Confident and practical" />
                      </label>
                      <label className="field">
                        <span>Brand personality</span>
                        <input value={form.brand_personality} onChange={(event) => updateForm("brand_personality", event.target.value)} placeholder="Modern, sharp, reliable" />
                      </label>
                    </div>
                  </section>

                  <section className="card-section">
                    <div className="section-head">
                      <h3>Assets & Proof</h3>
                      <p>Optional references that make the output more grounded.</p>
                    </div>
                    <div className="form-grid">
                      <label className="field">
                        <span>Logo URL</span>
                        <input value={form.company_logo_url} onChange={(event) => updateForm("company_logo_url", event.target.value)} placeholder="Optional logo reference" />
                      </label>
                      <div className="field">
                        <span>Logo upload</span>
                        <label className="file-upload-button">
                          <input type="file" accept="image/*" onChange={handleLogoUpload} />
                          Choose logo file
                        </label>
                      </div>
                      {logoPreviewUrl ? (
                        <div className="logo-preview field-full">
                          <img src={logoPreviewUrl} alt="Selected company logo" />
                          <div>
                            <strong>Logo ready</strong>
                            <span>{form.company_logo_url.startsWith("data:image") ? "Uploaded file will be sent with the brief." : "Logo URL will be sent with the brief."}</span>
                          </div>
                          <button type="button" className="ghost-button" onClick={() => updateForm("company_logo_url", "")}>Clear</button>
                        </div>
                      ) : null}
                      <label className="field field-full">
                        <span>Proof assets</span>
                        <textarea value={form.proof_assets} onChange={(event) => updateForm("proof_assets", event.target.value)} rows="3" placeholder="Case studies, testimonials, metrics" />
                      </label>
                    </div>
                  </section>

                  <div className="workflow-actions">
                    <button type="button" className="ghost-button" onClick={() => setActiveStep("Plan")}>Plan Week</button>
                    <button type="button" className="primary-button" onClick={(event) => handleGenerate(event, "both")} disabled={generateState.loading}>
                      {generateState.loading && generationMode === "both" ? "Generating..." : "Generate Content"}
                    </button>
                  </div>
                </form>
              </div>

              <div ref={sectionRefs.Plan} className={activeStep === "Plan" ? "workflow-panel active" : "workflow-panel"}>
                <div className="panel-head">
                  <div className="panel-title-row">
                    <div>
                      <h2>Weekly Plan</h2>
                      <p>Create a strategic weekly calendar and automatically generate every planned post.</p>
                    </div>
                    <span className="status-pill">Planning</span>
                  </div>
                </div>

                <form className="workflow-form" onSubmit={handleCreateWeeklyPlan}>
                  <section className="card-section">
                    <div className="section-head">
                      <h3>Weekly Campaign</h3>
                      <p>Use the business profile from the Brief section and add this week&apos;s campaign direction.</p>
                    </div>
                    <div className="form-grid">
                      <label className="field">
                        <span>Week start date</span>
                        <input type="date" value={weeklyPlanForm.week_start_date} onChange={(event) => updateWeeklyPlanForm("week_start_date", event.target.value)} />
                      </label>
                      <label className="field">
                        <span>Number of posts</span>
                        <select value={weeklyPlanForm.posts_count} onChange={(event) => updateWeeklyPlanForm("posts_count", event.target.value)}>
                          {[1, 2, 3, 4, 5, 6, 7].map((count) => (
                            <option key={count} value={count}>{count}</option>
                          ))}
                        </select>
                      </label>
                      <label className="field field-full">
                        <span>Weekly goal</span>
                        <input value={weeklyPlanForm.weekly_goal} onChange={(event) => updateWeeklyPlanForm("weekly_goal", event.target.value)} placeholder="Educate prospects and drive qualified conversations" />
                      </label>
                      <label className="field field-full">
                        <span>Theme</span>
                        <input value={weeklyPlanForm.theme} onChange={(event) => updateWeeklyPlanForm("theme", event.target.value)} placeholder="Faster lead follow-up with AI automation" />
                      </label>
                    </div>
                    <div className="platform-check-row">
                      {PLATFORMS.map((platform) => (
                        <button
                          key={platform}
                          type="button"
                          className={weeklyPlanForm.platforms.includes(platform) ? "platform-toggle active" : "platform-toggle"}
                          onClick={() => toggleWeeklyPlanPlatform(platform)}
                        >
                          {platform}
                        </button>
                      ))}
                    </div>
                    <div className="workflow-actions">
                      <button type="button" className="ghost-button" onClick={() => setActiveStep("Brief")}>Back to Brief</button>
                      <button type="submit" className="primary-button" disabled={contentPlanState.loading}>
                        {contentPlanState.loading ? "Planning + Generating..." : "Create Plan + Generate Posts"}
                      </button>
                    </div>
                    {contentPlanState.error ? <div className="alert error">{contentPlanState.error}</div> : null}
                  </section>
                </form>

                {contentPlanState.loading ? (
                  <div className="skeleton-grid">
                    <div className="skeleton-card" />
                    <div className="skeleton-card" />
                    <div className="skeleton-card" />
                  </div>
                ) : null}

                {contentPlanState.plan ? (
                  <section className="weekly-plan-grid">
                    {contentPlanState.plan.items.map((item) => (
                      <article key={`${contentPlanState.plan.plan_id}-${item.position}`} className="weekly-plan-card">
                        <div className="weekly-plan-card-head">
                          <span className="post-index-badge">Post {item.position}</span>
                          <div className="post-meta-row">
                            <span>{item.day}</span>
                            <span>{item.platform}</span>
                            <span>{item.content_type}</span>
                          </div>
                        </div>
                        <h3>{item.topic}</h3>
                        <div className="plan-detail-list">
                          <div><span>Angle</span><p>{item.angle}</p></div>
                          <div><span>Hook</span><p>{item.hook_direction}</p></div>
                          <div><span>CTA</span><p>{item.cta_direction}</p></div>
                          <div><span>Visual</span><p>{item.visual_direction}</p></div>
                        </div>
                        {item.generation_status === "completed" ? (
                          <div className="weekly-generated-preview">
                            <span className="status-pill connected">Generated</span>
                            <h4>{item.generated_headline || "Generated post"}</h4>
                            <p className="caption-text generated-caption">{item.generated_caption}</p>
                            {item.generated_image_url ? (
                              <button
                                type="button"
                                className="generated-post-image-button"
                                onClick={() => setImagePreview({
                                  src: absoluteUrl(item.generated_image_url),
                                  alt: item.generated_headline || `Generated post ${item.position}`,
                                  title: item.generated_headline || `Post ${item.position}`
                                })}
                              >
                                <img src={absoluteUrl(item.generated_image_url)} alt={item.generated_headline || `Generated post ${item.position}`} />
                              </button>
                            ) : null}
                          </div>
                        ) : null}
                        {item.generation_status === "failed" ? (
                          <div className="alert error">{item.generation_error || "This post failed to generate."}</div>
                        ) : null}
                        <div className="workflow-actions">
                          <button type="button" className="ghost-button" onClick={() => {
                            setForm((current) => ({
                              ...current,
                              weekly_focus_topic: `${item.topic}. Angle: ${item.angle}. Hook direction: ${item.hook_direction}. Visual direction: ${item.visual_direction}`,
                              day: item.day,
                              content_type: item.content_type,
                              platform: item.platform,
                              cta_preference: item.cta_direction || current.cta_preference
                            }));
                            setActiveStep("Brief");
                          }}>
                            Load Brief
                          </button>
                          {item.generation_status === "completed" ? (
                            <button type="button" className="primary-button" onClick={() => useGeneratedPost({
                              id: item.generated_post_id,
                              platform: item.platform,
                              day: item.day,
                              content_type: item.content_type,
                              topic: item.topic,
                              caption: item.generated_caption,
                              headline: item.generated_headline,
                              image_url: item.generated_image_url,
                              image_file_path: "",
                              alt_text: item.generated_headline,
                              status: "completed",
                              created_at: ""
                            })}>
                              Open in Review
                            </button>
                          ) : (
                            <button type="button" className="primary-button" onClick={() => generatePlanItem(item)} disabled={generateState.loading}>
                              Retry Generate
                            </button>
                          )}
                        </div>
                      </article>
                    ))}
                  </section>
                ) : (
                  <div className="empty-state compact">
                    <h3>No weekly plan yet</h3>
                    <p>Create a plan to generate a full week of unique posts automatically.</p>
                  </div>
                )}
              </div>

              <div ref={sectionRefs.Generate} className={activeStep === "Generate" ? "workflow-panel active" : "workflow-panel"}>
                <div className="panel-head">
                  <div className="panel-title-row">
                    <div>
                      <h2>Generate</h2>
                      <p>Create caption and image variations from the brief.</p>
                    </div>
                    <span className="status-pill">AI generation</span>
                  </div>
                </div>

                <section className="card-section">
                  <div className="section-head">
                    <h3>Generation settings</h3>
                    <p>Keep the controls compact and focused.</p>
                  </div>
                  <div className="form-grid">
                    <label className="field">
                      <span>Caption length</span>
                      <select defaultValue="Medium">
                        <option>Short</option>
                        <option>Medium</option>
                        <option>Long</option>
                      </select>
                    </label>
                    <label className="field">
                      <span>Image style</span>
                      <select defaultValue="Editorial">
                        <option>Editorial</option>
                        <option>Product</option>
                        <option>Bold</option>
                      </select>
                    </label>
                    <label className="field">
                      <span>Number of variations</span>
                      <select defaultValue="2">
                        <option>1</option>
                        <option>2</option>
                        <option>3</option>
                      </select>
                    </label>
                    <label className="field">
                      <span>Platform</span>
                      <select value={form.platform} onChange={(event) => updateForm("platform", event.target.value)}>
                        {PLATFORMS.map((item) => (
                          <option key={item} value={item}>
                            {item}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <div className="generation-actions">
                    <button type="button" className="ghost-button" onClick={(event) => handleGenerate(event, "caption") } disabled={generateState.loading}>
                      Generate Caption
                    </button>
                    <button type="button" className="ghost-button" onClick={(event) => handleGenerate(event, "image") } disabled={generateState.loading}>
                      Generate Image
                    </button>
                    <button type="button" className="primary-button" onClick={(event) => handleGenerate(event, "both") } disabled={generateState.loading}>
                      {generateState.loading && generationMode === "both" ? "Generating Both..." : "Generate Both"}
                    </button>
                    <button type="button" className="ghost-button" onClick={() => setActiveStep("Review")}>
                      Review Output
                    </button>
                  </div>
                  {generateState.loading ? (
                    <div className="skeleton-grid">
                      <div className="skeleton-card" />
                      <div className="skeleton-card" />
                      <div className="skeleton-card" />
                    </div>
                  ) : null}
                  {generateState.error ? <div className="alert error">{generateState.error}</div> : null}
                </section>

                {generateState.result ? (
                  <section className="variation-grid">
                    <div className="variation-card">
                      <span className="mini-label">Caption Variation 1</span>
                      <h3>{generateState.result.headline}</h3>
                      <p className="caption-text">{generateState.result.caption}</p>
                      <div className="inline-actions">
                        <button type="button" className="ghost-button" onClick={() => setActiveStep("Review")}>Use this version</button>
                        <button type="button" className="ghost-button" onClick={(event) => handleGenerate(event, "caption")}>Regenerate</button>
                      </div>
                    </div>
                    <div className="variation-card muted-card">
                      <span className="mini-label">Caption Variation 2</span>
                      <h3>Refined angle</h3>
                      <p className="caption-text">Generate again to compare a different tone, hook, or CTA if needed.</p>
                    </div>
                    <div className="variation-card image-card">
                      <span className="mini-label">Image Preview</span>
                      {generatedPreviewUrl ? (
                        <img src={generatedPreviewUrl} alt={generatedImage?.alt_text || "Generated social visual"} />
                      ) : (
                        <div className="preview-placeholder">Generating visual concept...</div>
                      )}
                    </div>
                  </section>
                ) : (
                  <div className="empty-state compact">
                    <h3>No content generated yet</h3>
                    <p>Generate a caption to preview your post and populate the review workspace.</p>
                  </div>
                )}
              </div>

              <div ref={sectionRefs.Review} className={activeStep === "Review" ? "workflow-panel active" : "workflow-panel"}>
                <div className="panel-head">
                  <div className="panel-title-row">
                    <div>
                      <h2>Review</h2>
                      <p>Refine the final caption and compare it against the post preview.</p>
                    </div>
                    <span className="status-pill">QA ready</span>
                  </div>
                </div>

                <div className="review-layout">
                  <section className="card-section">
                    <div className="section-head">
                      <h3>Caption editor</h3>
                      <p>Polish the final copy before publishing.</p>
                    </div>
                    <textarea className="editor" value={publishForm.caption || generateState.result?.caption || ""} onChange={(event) => updatePublishForm("caption", event.target.value)} rows="10" placeholder="Edit your final caption here" />
                    <div className="suggestion-row">
                      <span>#automation</span>
                      <span>#socialmedia</span>
                      <span>#growth</span>
                      <span>#productivity</span>
                    </div>
                    <div className="suggestion-row">
                      <span>Ready to book a call?</span>
                      <span>Try this workflow today</span>
                      <span>Want the template?</span>
                    </div>
                    <div className="workflow-actions">
                      <button type="button" className="ghost-button" onClick={() => setActiveStep("Generate")}>Back to Generate</button>
                      <button type="button" className="ghost-button" onClick={() => triggerToast("Content approved", "success")}>Approve Content</button>
                      <button type="button" className="primary-button" onClick={() => setActiveStep("Publish")}>Continue to Publish</button>
                    </div>
                  </section>

                  <section className="preview-section">
                    <div className="post-preview-card">
                      <div className="post-preview-head">
                        <div className="avatar large">GM</div>
                        <div>
                          <strong>{previewData.page}</strong>
                          <p>{previewData.network} - {previewData.timestamp}</p>
                        </div>
                      </div>
                      <h3>{previewData.headline}</h3>
                      <p className="caption-text">{previewData.body}</p>
                      {activePreviewUrl ? <img src={activePreviewUrl} alt="Selected publish asset" /> : <div className="preview-placeholder">Generate or upload an image to complete the preview.</div>}
                      <div className="engagement-row">
                        <span>Like</span>
                        <span>Comment</span>
                        <span>Share</span>
                        <span>Save</span>
                      </div>
                    </div>

                    <div className="checklist-card">
                      <span className="mini-label">QA Checklist</span>
                      <ul className="checklist">
                        <li>Caption has hook</li>
                        <li>CTA included</li>
                        <li>No spelling issues</li>
                        <li>Platform length is valid</li>
                        <li>Image available</li>
                        <li>Brand tone matched</li>
                      </ul>
                    </div>
                  </section>
                </div>
              </div>

              <div ref={sectionRefs.Publish} className={activeStep === "Publish" ? "workflow-panel active" : "workflow-panel"}>
                <div className="panel-head">
                  <div className="panel-title-row">
                    <div>
                      <h2>Publish</h2>
                      <p>Keep integrations hidden until needed, with a summary up front.</p>
                    </div>
                    <span className="status-pill">{publishMode === "schedule" ? "Scheduled" : "Publish now"}</span>
                  </div>
                </div>

                <form onSubmit={handlePublish} className="publish-grid">
                  <section className="card-section">
                    <div className="section-head">
                      <h3>Platform selection</h3>
                      <p>Choose where the post is going.</p>
                    </div>
                    <div className="platform-grid">
                      <button type="button" className={publishForm.platform === "facebook" ? "platform-card active" : "platform-card"} onClick={() => updatePublishForm("platform", "facebook")}>
                        <strong>Facebook Page</strong>
                        <span>Connected</span>
                      </button>
                      <button type="button" className={publishForm.platform === "instagram" ? "platform-card active" : "platform-card"} onClick={() => updatePublishForm("platform", "instagram")}>
                        <strong>Instagram Business</strong>
                        <span>{publishForm.instagram_business_account_id ? "Connected" : "Token required"}</span>
                      </button>
                      <button type="button" className="platform-card disabled" disabled>
                        <strong>LinkedIn Page</strong>
                        <span>Placeholder</span>
                      </button>
                    </div>
                  </section>

                  <section className="card-section">
                    <div className="section-head">
                      <h3>Publishing options</h3>
                      <p>Keep the primary action visible.</p>
                    </div>
                    <div className="form-grid">
                      <label className="field">
                        <span>Mode</span>
                        <select value={publishMode} onChange={(event) => setPublishMode(event.target.value)}>
                          <option value="now">Publish now</option>
                          <option value="schedule">Schedule for later</option>
                          <option value="draft">Save as draft</option>
                        </select>
                      </label>
                      <label className="field">
                        <span>Platform</span>
                        <select value={publishForm.platform} onChange={(event) => updatePublishForm("platform", event.target.value)}>
                          {PUBLISHABLE_PLATFORMS.map((item) => (
                            <option key={item} value={item}>
                              {item}
                            </option>
                          ))}
                        </select>
                      </label>
                      {publishMode === "schedule" ? (
                        <label className="field field-full">
                          <span>Date & time</span>
                          <input type="datetime-local" value={scheduledFor} onChange={(event) => setScheduledFor(event.target.value)} />
                        </label>
                      ) : null}
                    </div>
                  </section>

                  <section className="card-section">
                    <details className="advanced-accordion">
                      <summary>Advanced settings</summary>
                      <p>Only fill these if your platform connection needs overrides.</p>
                      <div className="form-grid advanced-grid">
                        <label className="field">
                          <span>Shared Meta access token</span>
                          <input type="password" value={publishForm.access_token} onChange={(event) => updatePublishForm("access_token", event.target.value)} placeholder="Use this if one token covers both accounts" />
                        </label>
                        <label className="field">
                          <span>Facebook Page ID</span>
                          <input value={publishForm.facebook_page_id} onChange={(event) => updatePublishForm("facebook_page_id", event.target.value)} placeholder="Required for Facebook" />
                        </label>
                        <label className="field">
                          <span>Facebook access token</span>
                          <input type="password" value={publishForm.facebook_access_token} onChange={(event) => updatePublishForm("facebook_access_token", event.target.value)} placeholder="Optional override" />
                        </label>
                        <label className="field">
                          <span>Instagram business account ID</span>
                          <input value={publishForm.instagram_business_account_id} onChange={(event) => updatePublishForm("instagram_business_account_id", event.target.value)} placeholder="Required for Instagram" />
                        </label>
                        <label className="field field-full">
                          <span>Instagram access token</span>
                          <input type="password" value={publishForm.instagram_access_token} onChange={(event) => updatePublishForm("instagram_access_token", event.target.value)} placeholder="Optional override if different from shared token" />
                        </label>
                      </div>
                    </details>
                  </section>

                  <section className="card-section">
                    <div className="section-head">
                      <h3>Final publish summary</h3>
                      <p>Quick check before sending or scheduling.</p>
                    </div>
                    <div className="summary-grid">
                      <div><span>Platform</span><strong>{activePlatformLabel}</strong></div>
                      <div><span>Business/page</span><strong>{form.business_name || "GrowMino"}</strong></div>
                      <div><span>Caption status</span><strong>{publishForm.caption || generateState.result?.caption ? "Ready" : "Missing"}</strong></div>
                      <div><span>Image status</span><strong>{activePreviewUrl ? "Ready" : "Missing"}</strong></div>
                      <div><span>Publishing mode</span><strong>{publishModeLabel}</strong></div>
                      <div><span>Token status</span><strong>{publishForm.access_token || publishForm.facebook_access_token || publishForm.instagram_access_token ? "Set" : "Required"}</strong></div>
                    </div>
                  </section>

                  <div className="workflow-actions">
                    <button type="button" className="ghost-button" onClick={() => setActiveStep("Review")}>Back to Review</button>
                    <button type="submit" className="primary-button" disabled={publishState.loading}>
                      {publishState.loading ? "Publishing..." : publishMode === "schedule" ? "Schedule Post" : "Publish Now"}
                    </button>
                  </div>
                </form>

                {publishState.error ? <div className="alert error">{publishState.error}</div> : null}
              </div>

              <div ref={sectionRefs.WeeklyPosts} className={activeStep === "WeeklyPosts" ? "workflow-panel weekly-posts-panel active" : "workflow-panel weekly-posts-panel"}>
                <div className="panel-head">
                  <div className="panel-title-row">
                    <div>
                      <h2>Weekly Posts</h2>
                      <p>Browse generated weekly content in a visual gallery with date and platform filters.</p>
                    </div>
                    <button type="button" className="ghost-button" onClick={loadGeneratedPosts} disabled={generatedPostsState.loading}>
                      {generatedPostsState.loading ? "Refreshing..." : "Refresh"}
                    </button>
                  </div>
                </div>

                <section className="card-section">
                  <div className="section-head">
                    <h3>Filters</h3>
                    <p>Use dates to narrow a specific weekly campaign window.</p>
                  </div>
                  <div className="form-grid">
                    <label className="field">
                      <span>From date</span>
                      <input type="date" value={weeklyPostFilters.date_from} onChange={(event) => setWeeklyPostFilters((current) => ({ ...current, date_from: event.target.value }))} />
                    </label>
                    <label className="field">
                      <span>To date</span>
                      <input type="date" value={weeklyPostFilters.date_to} onChange={(event) => setWeeklyPostFilters((current) => ({ ...current, date_to: event.target.value }))} />
                    </label>
                    <label className="field">
                      <span>Platform</span>
                      <select value={weeklyPostFilters.platform} onChange={(event) => setWeeklyPostFilters((current) => ({ ...current, platform: event.target.value }))}>
                        <option value="all">All platforms</option>
                        {PLATFORMS.map((platform) => (
                          <option key={platform} value={platform}>{platform}</option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      <span>Day</span>
                      <select value={weeklyPostFilters.day} onChange={(event) => setWeeklyPostFilters((current) => ({ ...current, day: event.target.value }))}>
                        <option value="all">All days</option>
                        {DAYS.map((day) => (
                          <option key={day} value={day}>{day}</option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <div className="workflow-actions">
                    <button type="button" className="ghost-button" onClick={() => setWeeklyPostFilters({ date_from: "", date_to: "", platform: "all", day: "all" })}>
                      Clear Filters
                    </button>
                    <span className="status-pill">{weeklyGalleryPosts.length} posts</span>
                  </div>
                </section>

                {generatedPostsState.error ? <div className="alert error">{generatedPostsState.error}</div> : null}

                {generatedPostsState.loading ? (
                  <div className="skeleton-grid">
                    <div className="skeleton-card" />
                    <div className="skeleton-card" />
                    <div className="skeleton-card" />
                  </div>
                ) : null}

                {!generatedPostsState.loading && !weeklyGalleryPosts.length ? (
                  <div className="empty-state compact">
                    <h3>No posts match these filters</h3>
                    <p>Generate weekly posts or adjust the date/platform filters.</p>
                  </div>
                ) : null}

                {!generatedPostsState.loading && weeklyGalleryPosts.length ? (
                  <div className="weekly-carousel-stage">
                    <div className="weekly-carousel-head">
                      <div>
                        <span className="eyebrow">Weekly gallery</span>
                        <h3>{visibleWeeklyStart}-{visibleWeeklyEnd} of {weeklyGalleryPosts.length} posts</h3>
                      </div>
                      <div className="weekly-carousel-controls">
                        <button type="button" className="carousel-arrow inline" aria-label="Previous weekly posts" onClick={() => scrollWeeklyCarousel("prev")} disabled={weeklyCarouselPage === 0}>
                          &#8249;
                        </button>
                        <div className="carousel-dots" aria-label="Weekly carousel pages">
                          {Array.from({ length: weeklyCarouselPageCount }).map((_, page) => (
                            <button
                              type="button"
                              key={page}
                              className={page === weeklyCarouselPage ? "carousel-dot active" : "carousel-dot"}
                              aria-label={`Show weekly posts page ${page + 1}`}
                              aria-current={page === weeklyCarouselPage ? "true" : undefined}
                              onClick={() => goToWeeklyCarouselPage(page)}
                            />
                          ))}
                        </div>
                        <button type="button" className="carousel-arrow inline" aria-label="Next weekly posts" onClick={() => scrollWeeklyCarousel("next")} disabled={weeklyCarouselPage >= weeklyCarouselPageCount - 1}>
                          &#8250;
                        </button>
                      </div>
                    </div>

                    <div className="carousel-shell advanced">
                      <button type="button" className="carousel-arrow left" aria-label="Previous weekly posts" onClick={() => scrollWeeklyCarousel("prev")} disabled={weeklyCarouselPage === 0}>
                        &#8249;
                      </button>
                      <section className="weekly-post-gallery" ref={weeklyPostsCarouselRef} onScroll={syncWeeklyCarouselPage}>
                        {weeklyGalleryPosts.map((post, index) => (
                          <article key={post.id} className="weekly-post-gallery-card">
                            <div className="weekly-post-gallery-image">
                              {post.image_url ? (
                                <button
                                  type="button"
                                  className="gallery-image-button"
                                  onClick={() => setImagePreview({
                                    src: absoluteUrl(post.image_url),
                                    alt: post.alt_text || post.headline || `Weekly post ${index + 1}`,
                                    title: post.headline || `Weekly Post ${index + 1}`
                                  })}
                                >
                                  <img className="gallery-image-backdrop" src={absoluteUrl(post.image_url)} alt="" aria-hidden="true" />
                                  <img className="gallery-image-main" src={absoluteUrl(post.image_url)} alt={post.alt_text || post.headline || `Weekly post ${index + 1}`} />
                                </button>
                              ) : (
                                <div className="preview-placeholder compact-placeholder">No image saved</div>
                              )}
                            </div>
                            <div className="weekly-post-gallery-body">
                              <div className="weekly-post-gallery-topline">
                                <span className="post-index-badge">Post {index + 1}</span>
                                <span>{post.created_at ? new Date(post.created_at).toLocaleDateString() : "Saved"}</span>
                              </div>
                              <div className="post-meta-row">
                                <span>{post.platform || "platform"}</span>
                                <span>{post.day || "day"}</span>
                                <span>{post.content_type || "content"}</span>
                              </div>
                              <h3>{post.headline || post.topic || "Generated post"}</h3>
                              <p className="caption-text generated-caption">{post.caption || "No caption saved for this post."}</p>
                              <div className="workflow-actions">
                                <button type="button" className="ghost-button" onClick={() => useGeneratedPost(post)}>
                                  Open in Review
                                </button>
                              </div>
                            </div>
                          </article>
                        ))}
                      </section>
                      <button type="button" className="carousel-arrow right" aria-label="Next weekly posts" onClick={() => scrollWeeklyCarousel("next")} disabled={weeklyCarouselPage >= weeklyCarouselPageCount - 1}>
                        &#8250;
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>

              <div ref={sectionRefs.Posts} className={activeStep === "Posts" ? "workflow-panel active" : "workflow-panel"}>
                <div className="panel-head">
                  <div className="panel-title-row">
                    <div>
                      <h2>Generated Posts</h2>
                      <p>Review previously generated captions and visuals saved in Supabase.</p>
                    </div>
                    <div className="carousel-actions">
                      <button type="button" className="ghost-button" onClick={loadGeneratedPosts} disabled={generatedPostsState.loading}>
                        {generatedPostsState.loading ? "Refreshing..." : "Refresh"}
                      </button>
                    </div>
                  </div>
                </div>

                {generatedPostsState.error ? <div className="alert error">{generatedPostsState.error}</div> : null}

                {generatedPostsState.loading ? (
                  <div className="skeleton-grid">
                    <div className="skeleton-card" />
                    <div className="skeleton-card" />
                    <div className="skeleton-card" />
                  </div>
                ) : null}

                {!generatedPostsState.loading && !generatedPostsState.error && !generatedPostsState.posts.length ? (
                  <div className="empty-state compact">
                    <h3>No saved posts yet</h3>
                    <p>Generate a post after Supabase is configured and it will appear here.</p>
                  </div>
                ) : null}

                {!generatedPostsState.loading && generatedPostsState.posts.length ? (
                  <div className="carousel-shell">
                    <button type="button" className="carousel-arrow left" aria-label="Previous generated posts" onClick={() => scrollCarousel(generatedPostsCarouselRef, "prev")} disabled={generatedPostsState.posts.length <= 2}>
                      &#8249;
                    </button>
                    <section className="generated-posts-grid" ref={generatedPostsCarouselRef}>
                      {generatedPostsState.posts.map((post, index) => (
                        <article key={post.id} className="generated-post-card">
                        <div className="generated-post-card-head">
                          <div className="post-index-badge">Post {index + 1}</div>
                          <div className="post-meta-row">
                            <span>{post.platform || "platform"}</span>
                            <span>{post.day || "day"}</span>
                            <span>{post.content_type || "content"}</span>
                          </div>
                        </div>

                        <div className="generated-social-post">
                          <div className="post-preview-head">
                            <div className="avatar large">GM</div>
                            <div>
                              <strong>GrowMino Publisher</strong>
                              <p>{titleCase(post.platform || "social")} - {post.created_at ? new Date(post.created_at).toLocaleString() : "Saved post"}</p>
                            </div>
                          </div>

                          <h3>{post.headline || post.topic || "Generated post"}</h3>
                          <p className="caption-text generated-caption">{post.caption || "No caption saved for this post."}</p>

                          {post.image_url ? (
                            <button
                              type="button"
                              className="generated-post-image-button"
                              onClick={() => setImagePreview({
                                src: absoluteUrl(post.image_url),
                                alt: post.alt_text || post.headline || `Generated post ${index + 1}`,
                                title: post.headline || `Post ${index + 1}`
                              })}
                            >
                              <img src={absoluteUrl(post.image_url)} alt={post.alt_text || post.headline || `Generated post ${index + 1}`} />
                            </button>
                          ) : (
                            <div className="preview-placeholder compact-placeholder">No image saved</div>
                          )}

                          <div className="engagement-row">
                            <span>Like</span>
                            <span>Comment</span>
                            <span>Share</span>
                            <span>Save</span>
                          </div>
                        </div>

                        <div className="generated-post-footer">
                          <span>{post.status || "saved"}</span>
                          <button type="button" className="ghost-button" onClick={() => useGeneratedPost(post)}>
                            Open in Review
                          </button>
                        </div>
                      </article>
                    ))}
                    </section>
                    <button type="button" className="carousel-arrow right" aria-label="Next generated posts" onClick={() => scrollCarousel(generatedPostsCarouselRef, "next")} disabled={generatedPostsState.posts.length <= 2}>
                      &#8250;
                    </button>
                  </div>
                ) : null}
              </div>
            </section>

          </main>
        </div>
      </div>

      {toast.message ? <div className={toast.type === "error" ? "toast error" : "toast"}>{toast.message}</div> : null}

      {publishSuccess ? (
        <div className="modal-backdrop" onClick={() => setPublishSuccess(null)}>
          <div className="modal-card" onClick={(event) => event.stopPropagation()}>
            <span className="mini-label">Publish success</span>
            <h3>Post published successfully</h3>
            <p>{publishSuccess.message}</p>
            <div className="summary-grid modal-summary">
              <div><span>Platform</span><strong>{publishSuccess.platform}</strong></div>
              <div><span>Time</span><strong>{publishSuccess.time}</strong></div>
            </div>
            <div className="workflow-actions modal-actions">
              <button type="button" className="ghost-button" onClick={() => setPublishSuccess(null)}>Close</button>
              <button type="button" className="primary-button" onClick={() => triggerToast("View post link placeholder", "success")}>View Post</button>
            </div>
          </div>
        </div>
      ) : null}

      {imagePreview ? (
        <div className="modal-backdrop image-modal-backdrop" onClick={() => setImagePreview(null)}>
          <div className="image-modal-card" onClick={(event) => event.stopPropagation()}>
            <div className="image-modal-head">
              <div>
                <span className="mini-label">Image preview</span>
                <h3>{imagePreview.title}</h3>
              </div>
              <button type="button" className="ghost-button" onClick={() => setImagePreview(null)}>Close</button>
            </div>
            <img src={imagePreview.src} alt={imagePreview.alt} />
          </div>
        </div>
      ) : null}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
