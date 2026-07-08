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

const PLATFORMS = ["linkedin", "instagram", "facebook"];
const PUBLISHABLE_PLATFORMS = ["facebook", "instagram"];
const STEPS = ["Brief", "Generate", "Review", "Publish"];

const SIDEBAR_ITEMS = [
  "Create Post",
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
  const sectionRefs = {
    Brief: React.useRef(null),
    Generate: React.useRef(null),
    Review: React.useRef(null),
    Publish: React.useRef(null)
  };
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

  function updateForm(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function updatePublishForm(field, value) {
    setPublishForm((current) => ({ ...current, [field]: value }));
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
    if (item === "Content Calendar" || item === "Drafts") {
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

  function applyPreset(nextPreset) {
    setPreset(nextPreset);
    setForm({ ...PRESETS[nextPreset] });
    triggerToast(`${nextPreset} preset loaded`, "success");
  }

  async function handleGenerate(event, mode = "both") {
    event.preventDefault();
    setGenerationMode(mode);
    setActiveStep("Generate");
    setGenerateState({ loading: true, error: "", result: null });
    setPublishState({ loading: false, error: "", success: "" });
    setPublishSuccess(null);

    try {
      const response = await fetch(`${API_BASE_URL}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form)
      });
      const payload = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(payload?.detail || "Generation failed.");
      }

      setGenerateState({ loading: false, error: "", result: payload });
      setPublishForm((current) => ({
        ...current,
        platform: PUBLISHABLE_PLATFORMS.includes(payload?.meta?.platform) ? payload.meta.platform : "facebook",
        caption: payload?.caption || current.caption,
        image_url: "",
        uploadedFile: null
      }));
      triggerToast("Content generated", "success");
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

    const response = await fetch(`${API_BASE_URL}/upload-image`, {
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
      const response = await fetch(`${API_BASE_URL}/publish-meta`, {
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
                  (item === "Create Post" && activeStep === "Brief") || (item === "Integrations" && activeStep === "Publish")
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
                  <button key={step} type="button" className={active ? "stepper-step active" : complete ? "stepper-step complete" : "stepper-step"} onClick={() => setActiveStep(step)}>
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
                        <span>Content type</span>
                        <select value={form.content_type} onChange={(event) => updateForm("content_type", event.target.value)}>
                          {CONTENT_TYPES.map((item) => (
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
                        <span>Logo URL or upload</span>
                        <input value={form.company_logo_url} onChange={(event) => updateForm("company_logo_url", event.target.value)} placeholder="Optional logo reference" />
                      </label>
                      <label className="field field-full">
                        <span>Proof assets</span>
                        <textarea value={form.proof_assets} onChange={(event) => updateForm("proof_assets", event.target.value)} rows="3" placeholder="Case studies, testimonials, metrics" />
                      </label>
                    </div>
                  </section>

                  <div className="workflow-actions">
                    <button type="button" className="ghost-button" onClick={() => setActiveStep("Generate")}>Continue to Generate</button>
                    <button type="button" className="primary-button" onClick={(event) => handleGenerate(event, "both")} disabled={generateState.loading}>
                      {generateState.loading && generationMode === "both" ? "Generating..." : "Generate Content"}
                    </button>
                  </div>
                </form>
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
            </section>

            <aside className="preview-column">
              <div className="sticky-card">
                <div className="card-section">
                  <div className="section-head">
                    <h3>Integration status</h3>
                    <p>What the current publish connection looks like.</p>
                  </div>
                  <div className="status-list">
                    <div><span>Facebook</span><strong>{publishForm.facebook_page_id ? "Connected" : "Token required"}</strong></div>
                    <div><span>Instagram</span><strong>{publishForm.instagram_business_account_id ? "Connected" : "Token required"}</strong></div>
                    <div><span>Image source</span><strong>{publishForm.uploadedFile ? "Uploaded" : generatedPreviewUrl ? "Generated" : "Missing"}</strong></div>
                  </div>
                </div>
              </div>
            </aside>
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
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
