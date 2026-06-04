"use client";

import React, { useState, useEffect } from "react";
import {
  Play,
  Download,
  Sparkles,
  Film,
  CreditCard,
  Check,
  Lock,
  Flame,
  Clock,
  ArrowRight,
  AlertCircle,
  CheckCircle2,
  X,
  Loader2,
  RefreshCw,
  Sliders,
  Zap,
  ChevronRight,
  LockKeyhole
} from "lucide-react";

// Self-contained YouTube SVG Icon
const YoutubeIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth="2"
    fill="none"
    strokeLinecap="round"
    strokeLinejoin="round"
    {...props}
  >
    <path d="M22.54 6.42a2.78 2.78 0 0 0-1.95-1.96C18.88 4 12 4 12 4s-6.88 0-8.59.46a2.78 2.78 0 0 0-1.95 1.96A29 29 0 0 0 1 11.54a29 29 0 0 0 .46 5.12 2.78 2.78 0 0 0 1.95 1.96c1.71.46 8.59.46 8.59.46s6.88 0 8.59-.46a2.78 2.78 0 0 0 1.95-1.96 29 29 0 0 0 .46-5.12 29 29 0 0 0-.46-5.12z" />
    <polygon points="9.75 15.02 15.5 11.54 9.75 8.06 9.75 15.02" fill="currentColor" />
  </svg>
);

// Configured Backend URL
const BACKEND_URL = "http://localhost:8000";

interface VideoInfo {
  title: string;
  duration: number;
  thumbnail: string;
  id: string;
  webpage_url: string;
}

interface Clip {
  id: string;
  suggested_title: string;
  rationale: string;
  title: string;
  reasoning: string;
  transcript_segment: string;
  start_time: string;
  end_time: string;
  start_seconds: number;
  end_seconds: number;
  virality_score: number;
}

interface Subscription {
  plan: string;
  credits: number;
  active: boolean;
}

export default function HookFlowApp() {
  // App States
  const [url, setUrl] = useState("");
  const [videoInfo, setVideoInfo] = useState<VideoInfo | null>(null);
  const [isFetchingInfo, setIsFetchingInfo] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);

  // Studio Settings
  const [apiKey, setApiKey] = useState("");
  const [selectedModel, setSelectedModel] = useState("gemini-2.5-flash");
  const [numClips, setNumClips] = useState(3);
  const [showSettings, setShowSettings] = useState(false);

  // Analysis States
  const [clips, setClips] = useState<Clip[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisStep, setAnalysisStep] = useState(0); // 1 = Audio Download, 2 = AI Processing

  // Render & Gallery States
  const [activeClipIdx, setActiveClipIdx] = useState(0);
  const [renderedClips, setRenderedClips] = useState<{ [key: number]: string }>({});
  const [renderingClipIdx, setRenderingClipIdx] = useState<number | null>(null);
  const [renderProgress, setRenderProgress] = useState(0);
  const [renderStatusText, setRenderStatusText] = useState("");

  // Subscription States (Stripe Sandbox)
  const [subscription, setSubscription] = useState<Subscription>({
    plan: "Free",
    credits: 3,
    active: true
  });
  const [checkoutPlan, setCheckoutPlan] = useState<{ name: string; price: number } | null>(null);
  const [isProcessingPayment, setIsProcessingPayment] = useState(false);
  const [paymentSuccess, setPaymentSuccess] = useState(false);
  const [cardNumber, setCardNumber] = useState("");
  const [cardExpiry, setCardExpiry] = useState("");
  const [cardCvc, setCardCvc] = useState("");
  const [cardName, setCardName] = useState("");

  // Fetch current user subscription state on load
  useEffect(() => {
    fetchSubscription();
  }, []);

  const fetchSubscription = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/stripe/subscription`);
      if (res.ok) {
        const data = await res.json();
        setSubscription(data);
      }
    } catch (err) {
      console.error("Failed to fetch subscription status:", err);
    }
  };

  // Reset subscription to Free (For testing sandbox)
  const handleResetCredits = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/stripe/reset-credits`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setSubscription(data);
        // Clear workspace
        setClips([]);
        setVideoInfo(null);
        setUrl("");
        setRenderedClips({});
        setActiveClipIdx(0);
      }
    } catch (err) {
      console.error("Reset failed:", err);
    }
  };

  // Fetch YouTube Metadata
  const handleFetchMetadata = async () => {
    if (!url.trim()) return;
    setIsFetchingInfo(true);
    setErrorText(null);
    setVideoInfo(null);
    setClips([]);
    setRenderedClips({});
    
    try {
      const res = await fetch(`${BACKEND_URL}/api/video-info`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url })
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to fetch video information.");
      }
      const data = await res.json();
      setVideoInfo(data);
    } catch (err: any) {
      setErrorText(err.message || "Something went wrong fetching metadata.");
    } finally {
      setIsFetchingInfo(false);
    }
  };

  // Run Gemini Virality Analysis
  const handleAnalyzeVideo = async () => {
    if (!url || !videoInfo) return;
    
    // Credit check
    if (subscription.plan === "Free" && subscription.credits <= 0) {
      setErrorText("You have run out of credits. Please upgrade to a premium plan below!");
      const pricingSec = document.getElementById("pricing-section");
      if (pricingSec) pricingSec.scrollIntoView({ behavior: "smooth" });
      return;
    }

    setIsAnalyzing(true);
    setErrorText(null);
    setAnalysisStep(1); // Audio downloading...

    // Simulate standard progress bar while processing
    const progressInterval = setInterval(() => {
      setAnalysisStep((prev) => (prev === 1 ? 1 : 2));
    }, 4000);

    try {
      const res = await fetch(`${BACKEND_URL}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url,
          num_clips: numClips,
          api_key: apiKey || null,
          model: selectedModel
        })
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "AI analysis failed.");
      }

      const data = await res.json();
      setClips(data.clips || []);
      setActiveClipIdx(0);
      
      // Refresh credits after analysis (since it consumes credit in simulated backend)
      // For mock simplicity, we decrease credits locally too
      setSubscription(prev => ({
        ...prev,
        credits: prev.plan === "Free" ? Math.max(0, prev.credits - 1) : prev.plan === "Creator" ? Math.max(0, prev.credits - 1) : prev.credits
      }));
      
    } catch (err: any) {
      let errMsg = err.message || "AI Analysis failed.";
      if (errMsg.includes("429") || errMsg.includes("RESOURCE_EXHAUSTED") || errMsg.includes("quota")) {
        errMsg = "Gemini API Quota Exceeded (429). The server's key has reached its limit. To continue, click 'Show Studio Options' at the top-right and paste your own Gemini API Key.";
      }
      setErrorText(errMsg);
    } finally {
      clearInterval(progressInterval);
      setIsAnalyzing(false);
      setAnalysisStep(0);
    }
  };

  // Render Video Clip using MoviePy + FFmpeg
  const handleRenderClip = async (idx: number) => {
    const clip = clips[idx];
    if (!clip || !url) return;

    setRenderingClipIdx(idx);
    setRenderProgress(10);
    setRenderStatusText("Downloading high-quality range stream...");

    // Simulate progress updates for UI feedback
    const progressTimer = setInterval(() => {
      setRenderProgress((prev) => {
        if (prev < 40) {
          setRenderStatusText("Downloading segment range...");
          return prev + 5;
        } else if (prev < 75) {
          setRenderStatusText("Cropping frame to central 9:16 vertical mobile aspect ratio...");
          return prev + 3;
        } else if (prev < 95) {
          setRenderStatusText("Encoding video & burning yellow subtitle hook title...");
          return prev + 2;
        }
        return prev;
      });
    }, 1500);

    try {
      const res = await fetch(`${BACKEND_URL}/api/render`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url,
          clip_idx: idx,
          id: clip.id,
          start_time: clip.start_time,
          end_time: clip.end_time,
          start_seconds: clip.start_seconds,
          end_seconds: clip.end_seconds,
          title: clip.suggested_title || clip.title,
          api_key: apiKey || null,
          model: selectedModel
        })
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Rendering pipeline failed.");
      }

      const data = await res.json();
      setRenderProgress(100);
      setRenderStatusText("Render complete!");
      
      // Save rendered filename
      setRenderedClips((prev) => ({
        ...prev,
        [idx]: data.filename
      }));
    } catch (err: any) {
      let errMsg = err.message || "Rendering failed.";
      if (errMsg.includes("429") || errMsg.includes("RESOURCE_EXHAUSTED") || errMsg.includes("quota")) {
        alert("Gemini API Quota Exceeded (429). The server's key has reached its limit. Please click 'Show Studio Options' at the top-right and paste your own Gemini API Key to render this clip.");
      } else {
        alert(`Render failed: ${errMsg}`);
      }
    } finally {
      clearInterval(progressTimer);
      // Brief delay to show 100% completion
      setTimeout(() => {
        setRenderingClipIdx(null);
        setRenderProgress(0);
        setRenderStatusText("");
      }, 1000);
    }
  };

  // Simulated Stripe Payment Flow
  const triggerCheckout = (planName: string, price: number) => {
    setCheckoutPlan({ name: planName, price });
    setCardNumber("");
    setCardExpiry("");
    setCardCvc("");
    setCardName("");
  };

  const handleProcessPayment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!checkoutPlan) return;

    setIsProcessingPayment(true);
    
    // Simulate API checkout session generation and token verification (1.5s delay)
    setTimeout(async () => {
      try {
        // Trigger simulated Stripe webhook fulfillment call
        const webhookRes = await fetch(`${BACKEND_URL}/api/stripe/webhook`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            event_type: "checkout.session.completed",
            session_id: `cs_test_${Math.random().toString(36).substr(2, 9)}`,
            plan_name: checkoutPlan.name
          })
        });

        if (webhookRes.ok) {
          await fetchSubscription();
          setIsProcessingPayment(false);
          setCheckoutPlan(null);
          setPaymentSuccess(true);
        } else {
          throw new Error("Webhook simulation failed");
        }
      } catch (err) {
        alert("Payment simulation failed. Please try again.");
        setIsProcessingPayment(false);
      }
    }, 1500);
  };

  const activeClip = clips[activeClipIdx];
  const activeVideoFilename = renderedClips[activeClipIdx];

  return (
    <div className="flex-1 flex flex-col">
      {/* HEADER / NAVBAR */}
      <header className="sticky top-0 z-40 bg-brand-bg/85 backdrop-blur-md border-b border-artlist-border px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-accent-amber to-accent-neon flex items-center justify-center shadow-lg shadow-accent-amber/20">
            <Zap className="w-6 h-6 text-black fill-current" />
          </div>
          <div>
            <span className="font-extrabold text-xl tracking-tight text-white">
              HOOKFLOW <span className="text-accent-neon">AI</span>
            </span>
            <div className="text-[10px] text-accent-amber font-mono font-bold leading-none tracking-widest">
              STUDIO EDITION
            </div>
          </div>
        </div>

        <nav className="hidden md:flex items-center gap-8 text-sm font-semibold tracking-wide text-gray-300">
          <a href="#hero-section" className="hover:text-white transition-colors">Home</a>
          <a href="#studio-section" className="hover:text-white transition-colors">Workspace</a>
          <a href="#pricing-section" className="hover:text-white transition-colors">Pricing</a>
          <div className="w-[1px] h-4 bg-artlist-border" />
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 font-mono">Simulated Tier:</span>
            <span className="bg-brand-panel-light border border-artlist-border rounded-full py-1 px-3 text-xs font-bold text-accent-amber flex items-center gap-1.5 shadow-sm">
              <Sparkles className="w-3 h-3 text-accent-neon" />
              {subscription.plan.toUpperCase()}
            </span>
          </div>
        </nav>

        <div className="flex items-center gap-4">
          <div className="text-right hidden sm:block">
            <div className="text-xs text-gray-400 font-semibold">Credits Available:</div>
            <div className="text-sm font-extrabold font-mono text-white flex items-center justify-end gap-1">
              {subscription.plan === "Pro" ? "UNLIMITED" : `${subscription.credits} clips`}
            </div>
          </div>

          {subscription.plan !== "Free" && (
            <button
              onClick={handleResetCredits}
              className="text-xs text-gray-400 hover:text-white border border-artlist-border rounded px-2.5 py-1.5 transition-all hover:bg-brand-panel-light flex items-center gap-1 font-semibold"
              title="Reset state back to Free Plan for evaluation"
            >
              <RefreshCw className="w-3 h-3" /> Reset Demo
            </button>
          )}

          <a
            href="#studio-section"
            className="bg-accent-neon hover:bg-accent-neon-hover text-black font-extrabold py-2.5 px-5 rounded-lg text-sm transition-all shadow-md hover:shadow-accent-neon/30 active:scale-95"
          >
            Launch Studio
          </a>
        </div>
      </header>

      {/* HERO SECTION */}
      <section
        id="hero-section"
        className="relative overflow-hidden bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-brand-panel/20 via-brand-bg to-brand-bg py-20 px-6 border-b border-artlist-border"
      >
        <div className="max-w-6xl mx-auto text-center relative z-10">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-brand-panel border border-artlist-border text-xs font-semibold text-accent-amber mb-6 shadow-sm">
            <Flame className="w-4.5 h-4.5 text-accent-neon fill-current" />
            Cloning the sleek aesthetics of Artlist.io
          </div>

          <h1 className="text-4xl sm:text-6xl font-black tracking-tight text-white mb-6 leading-tight uppercase">
            Next-Gen AI Video Trimming.<br />
            <span className="text-gradient-amber">Hook Your Audience.</span>
          </h1>

          <p className="max-w-2xl mx-auto text-gray-400 text-base sm:text-lg mb-10 leading-relaxed font-medium">
            Turn long-form YouTube videos into highly engaging vertical Shorts, Reels & TikToks. Automated 9:16 central reframing, AI virality scoring, and styled burned-in hooks in a single click.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <a
              href="#studio-section"
              className="w-full sm:w-auto bg-accent-amber hover:bg-accent-amber-hover text-black font-extrabold text-base py-4 px-8 rounded-lg transition-all shadow-xl hover:shadow-accent-amber/20 flex items-center justify-center gap-2"
            >
              Launch Studio Workspace
              <ArrowRight className="w-5 h-5" />
            </a>
            <a
              href="#pricing-section"
              className="w-full sm:w-auto bg-brand-panel hover:bg-brand-panel-light text-white border border-artlist-border font-extrabold text-base py-4 px-8 rounded-lg transition-all flex items-center justify-center gap-2"
            >
              View Pricing Tiers
            </a>
          </div>

          <div className="mt-16 flex items-center justify-center gap-8 sm:gap-16 text-gray-400 text-xs sm:text-sm font-semibold tracking-wider uppercase border-t border-artlist-border/30 pt-10">
            <div className="flex items-center gap-2">
              <Check className="text-accent-neon w-5 h-5" /> Auto 9:16 Crop
            </div>
            <div className="flex items-center gap-2">
              <Check className="text-accent-neon w-5 h-5" /> Whisper Transcription
            </div>
            <div className="flex items-center gap-2">
              <Check className="text-accent-neon w-5 h-5" /> Gemini Analysis
            </div>
          </div>
        </div>

        {/* Ambient background decoration */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-accent-neon/5 blur-[120px] rounded-full pointer-events-none" />
      </section>

      {/* INTERACTIVE STUDIO WORKSPACE */}
      <section id="studio-section" className="py-16 px-4 md:px-8 max-w-7xl mx-auto w-full">
        <div className="mb-8 flex flex-col md:flex-row items-start md:items-end justify-between gap-4">
          <div>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-white uppercase tracking-tight flex items-center gap-2">
              <Film className="w-7 h-7 text-accent-neon" /> Interactive Studio Workspace
            </h2>
            <p className="text-gray-400 text-sm mt-1">
              Select YouTube video, configure viral hooks parameters, and render vertical shorts output.
            </p>
          </div>

          {/* Configuration Settings Button */}
          <button
            onClick={() => setShowSettings(!showSettings)}
            className={`flex items-center gap-2 text-xs font-bold border rounded-lg px-4 py-2 transition-all ${
              showSettings
                ? "bg-accent-amber border-accent-amber text-black"
                : "bg-brand-panel border-artlist-border text-gray-300 hover:bg-brand-panel-light hover:text-white"
            }`}
          >
            <Sliders className="w-4 h-4" />
            {showSettings ? "Hide Studio Options" : "Show Studio Options"}
          </button>
        </div>

        {/* Studio Options Panel */}
        {showSettings && (
          <div className="mb-8 bg-brand-panel border border-artlist-border rounded-xl p-6 grid grid-cols-1 md:grid-cols-3 gap-6 shadow-2xl relative overflow-hidden">
            <div className="flex flex-col gap-2">
              <label className="text-xs font-bold text-gray-300 uppercase tracking-wider">Gemini Model</label>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="bg-brand-bg border border-artlist-border rounded-lg py-2 px-3 text-sm text-white font-medium focus:outline-none focus:border-accent-neon"
              >
                <option value="gemini-2.5-flash">gemini-2.5-flash (Fast, Recommended)</option>
                <option value="gemini-2.5-pro">gemini-2.5-pro (High Quality, Slower)</option>
                <option value="gemini-1.5-flash">gemini-1.5-flash</option>
              </select>
              <span className="text-[10px] text-gray-500 font-medium">Controls the AI parsing the transcription.</span>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-xs font-bold text-gray-300 uppercase tracking-wider">Gemini API Key</label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Enter custom API key (or default server key)"
                className="bg-brand-bg border border-artlist-border rounded-lg py-2 px-3 text-sm text-white focus:outline-none focus:border-accent-neon"
              />
              <span className="text-[10px] text-gray-500 font-medium">Leave empty to use backend's GEMINI_API_KEY value.</span>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-xs font-bold text-gray-300 uppercase tracking-wider flex justify-between">
                <span>Max Clips to Find</span>
                <span className="text-accent-neon font-mono">{numClips}</span>
              </label>
              <input
                type="range"
                min="1"
                max="5"
                value={numClips}
                onChange={(e) => setNumClips(parseInt(e.target.value))}
                className="accent-accent-neon py-2 bg-transparent"
              />
              <span className="text-[10px] text-gray-500 font-medium">Select how many high-virality segments to extract.</span>
            </div>
          </div>
        )}

        {/* INPUT URL BOX */}
        <div className="bg-brand-panel border border-artlist-border rounded-xl p-6 mb-10 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 left-0 h-[3px] w-2/3 bg-gradient-to-r from-accent-neon to-accent-amber" />
          <h3 className="text-sm font-bold text-white uppercase tracking-wider mb-3 flex items-center gap-2">
            <YoutubeIcon className="w-5 h-5 text-red-500 fill-current" /> Paste YouTube Video Link
          </h3>
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="e.g. https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                className="w-full bg-brand-bg/80 border border-artlist-border focus:border-accent-neon/80 rounded-lg py-3.5 pl-4 pr-10 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-accent-neon"
              />
            </div>
            <button
              onClick={handleFetchMetadata}
              disabled={isFetchingInfo || !url}
              className="bg-brand-panel-light hover:bg-brand-panel border border-artlist-border hover:border-gray-500 text-white font-extrabold text-sm px-6 py-3.5 rounded-lg transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isFetchingInfo ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-accent-neon" />
                  Loading...
                </>
              ) : (
                "Load Video"
              )}
            </button>
          </div>

          {errorText && (
            <div className="mt-4 bg-red-950/30 border border-red-500/30 rounded-lg p-4 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
              <div className="text-xs font-semibold text-red-200">{errorText}</div>
            </div>
          )}

          {/* Metadata Display / Action Panel */}
          {videoInfo && (
            <div className="mt-6 border-t border-artlist-border/40 pt-6 flex flex-col md:flex-row items-center justify-between gap-6">
              <div className="flex items-center gap-4 w-full md:w-auto">
                <div className="relative w-28 aspect-video rounded-lg overflow-hidden border border-artlist-border shrink-0">
                  <img
                    src={videoInfo.thumbnail || "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe"}
                    alt={videoInfo.title}
                    className="w-full h-full object-cover"
                  />
                  <div className="absolute bottom-1 right-1 bg-black/85 text-[10px] font-mono text-white px-1.5 py-0.5 rounded font-bold">
                    {Math.floor(videoInfo.duration / 60)}m {videoInfo.duration % 60}s
                  </div>
                </div>
                <div className="min-w-0">
                  <h4 className="text-sm font-extrabold text-white truncate max-w-[300px] sm:max-w-[450px]">
                    {videoInfo.title}
                  </h4>
                  <a
                    href={videoInfo.webpage_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[11px] text-accent-amber font-mono font-bold hover:underline flex items-center gap-1 mt-1"
                  >
                    Watch Original <ChevronRight className="w-3 h-3" />
                  </a>
                </div>
              </div>

              {clips.length === 0 && (
                <button
                  onClick={handleAnalyzeVideo}
                  disabled={isAnalyzing}
                  className="w-full md:w-auto bg-gradient-to-r from-accent-neon to-accent-amber text-black font-black text-sm py-3.5 px-8 rounded-lg transition-all hover:brightness-110 flex items-center justify-center gap-2 shadow-lg shadow-accent-neon/10 disabled:opacity-50 disabled:cursor-not-allowed active:scale-95"
                >
                  {isAnalyzing ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin text-black" />
                      {analysisStep === 1
                        ? "Downloading audio stream..."
                        : "AI is analyzing audio transcription for hooks..."}
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4.5 h-4.5 fill-current" />
                      Analyze Viral Moments ({numClips} Clips)
                    </>
                  )}
                </button>
              )}
            </div>
          )}
        </div>

        {/* SPLIT SCREEN INTERACTIVE WORKSPACE */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          
          {/* LEFT PANEL: AI ANALYTICS PANEL */}
          <div className="lg:col-span-7 flex flex-col gap-6">
            <div className="bg-brand-panel border border-artlist-border rounded-xl p-6 shadow-2xl">
              <h3 className="text-sm font-extrabold text-white uppercase tracking-wider mb-4 border-b border-artlist-border/40 pb-3 flex items-center justify-between">
                <span>AI Analytics Panel</span>
                {clips.length > 0 && (
                  <span className="text-xs font-mono font-bold text-accent-neon">
                    {clips.length} moments detected
                  </span>
                )}
              </h3>

              {clips.length === 0 ? (
                <div className="py-20 text-center text-gray-500 font-medium flex flex-col items-center gap-3">
                  <div className="w-12 h-12 rounded-full border border-dashed border-artlist-border flex items-center justify-center text-xl text-gray-600">
                    🔍
                  </div>
                  <p className="text-sm">
                    Enter a YouTube URL above and select <b className="text-gray-400">Analyze</b> to generate clips analytics.
                  </p>
                </div>
              ) : (
                <div className="flex flex-col gap-4">
                  {clips.map((clip, index) => {
                    const isSelected = activeClipIdx === index;
                    const isRendered = renderedClips[index] !== undefined;
                    const isRendering = renderingClipIdx === index;
                    
                    return (
                      <div
                        key={index}
                        onClick={() => setActiveClipIdx(index)}
                        className={`group border rounded-xl p-4 cursor-pointer transition-all duration-300 relative overflow-hidden ${
                          isSelected
                            ? "bg-brand-panel-light/35 border-accent-neon/80 shadow-md shadow-accent-neon/5"
                            : "bg-brand-bg/40 border-artlist-border hover:border-gray-500"
                        }`}
                      >
                        {isSelected && (
                          <div className="absolute top-0 left-0 bottom-0 w-[4px] bg-accent-neon" />
                        )}

                        <div className="flex items-start justify-between gap-4 mb-2">
                          <div className="flex items-center gap-2">
                            <span className={`text-[10px] uppercase font-black px-2.5 py-1 rounded-full ${
                              isSelected ? "bg-accent-neon text-black" : "bg-brand-panel-light text-gray-400"
                            }`}>
                              Moments #{index + 1}
                            </span>
                            <span className="bg-red-500/10 border border-red-500/20 text-red-500 font-mono text-[10px] font-bold px-2 py-0.5 rounded flex items-center gap-1">
                              <Flame className="w-3 h-3 fill-current" />
                              {clip.virality_score}% Virality
                            </span>
                          </div>
                          
                          <div className="text-xs text-gray-400 font-mono font-bold flex items-center gap-1 shrink-0">
                            <Clock className="w-3.5 h-3.5 text-gray-500" />
                            {clip.start_time} - {clip.end_time}
                          </div>
                        </div>

                        <h4 className="text-sm font-extrabold text-white group-hover:text-accent-neon transition-colors mb-2 uppercase">
                          {clip.title}
                        </h4>

                        {isSelected && (
                          <div className="mt-4 pt-4 border-t border-artlist-border/40 text-xs flex flex-col gap-3.5 transition-all">
                            <div>
                              <span className="text-[10px] text-accent-amber uppercase font-black tracking-wider block mb-1">
                                Virality Reasoning
                              </span>
                              <p className="text-gray-300 leading-relaxed font-medium">
                                {clip.reasoning}
                              </p>
                            </div>
                            
                            <div>
                              <span className="text-[10px] text-accent-neon uppercase font-black tracking-wider block mb-1">
                                Transcript Highlight
                              </span>
                              <div className="bg-brand-bg/80 border border-artlist-border rounded-lg p-3 font-mono text-[11px] text-gray-400 leading-relaxed">
                                "{clip.transcript_segment}"
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Rendering / Play buttons */}
                        <div className="mt-4 flex items-center justify-end gap-2.5">
                          {isRendered ? (
                            <span className="text-[11px] font-bold text-accent-neon border border-accent-neon/30 bg-accent-neon/5 rounded-full py-1.5 px-3 flex items-center gap-1.5 shadow-sm">
                              <CheckCircle2 className="w-3.5 h-3.5 fill-current text-accent-neon" />
                              Rendered
                            </span>
                          ) : isRendering ? (
                            <div className="w-full flex flex-col gap-1.5 mt-2">
                              <div className="flex justify-between items-center text-[10px] font-bold text-gray-400 font-mono">
                                <span>{renderStatusText}</span>
                                <span>{renderProgress}%</span>
                              </div>
                              <div className="w-full h-1.5 bg-brand-bg rounded-full overflow-hidden border border-artlist-border">
                                <div
                                  className="h-full bg-accent-neon transition-all duration-300"
                                  style={{ width: `${renderProgress}%` }}
                                />
                              </div>
                            </div>
                          ) : (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleRenderClip(index);
                              }}
                              className="bg-brand-panel-light hover:bg-brand-panel text-white border border-artlist-border hover:border-gray-500 font-bold text-xs py-2 px-4 rounded-lg transition-all flex items-center gap-1.5 shadow-sm"
                            >
                              <Play className="w-3.5 h-3.5 text-accent-neon fill-current" />
                              Render Vertical Short (9:16) 🎬
                            </button>
                          )}
                        </div>

                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* RIGHT PANEL: 9:16 VERTICAL VIDEO PLAYER */}
          <div className="lg:col-span-5">
            <div className="bg-brand-panel border border-artlist-border rounded-xl p-6 shadow-2xl text-center flex flex-col items-center">
              <h3 className="text-sm font-extrabold text-white uppercase tracking-wider mb-6 border-b border-artlist-border/40 pb-3 w-full text-left">
                🎥 9:16 Vertical Preview
              </h3>

              {/* 9:16 Container (styled like phone framework) */}
              <div className="relative w-64 aspect-[9/16] bg-brand-bg rounded-[32px] border-4 border-artlist-border shadow-2xl overflow-hidden flex flex-col justify-between items-center group mb-6">
                
                {/* Simulated Phone Notch */}
                <div className="absolute top-2 w-28 h-4.5 bg-artlist-border rounded-full z-20 flex items-center justify-center">
                  <div className="w-2.5 h-2.5 bg-black rounded-full" />
                </div>

                {activeVideoFilename ? (
                  // Active Rendered Video Player
                  <video
                    src={`${BACKEND_URL}/api/stream/${activeVideoFilename}`}
                    controls
                    className="w-full h-full object-cover z-10"
                    playsInline
                    autoPlay
                    loop
                  />
                ) : activeClip ? (
                  // Stage 1: Lightweight Raw Video Preview
                  <iframe
                    src={`https://www.youtube.com/embed/${videoInfo?.id}?start=${Math.floor(activeClip.start_seconds)}&autoplay=1&mute=1`}
                    className="w-full h-full object-cover z-10 border-0"
                    allow="autoplay; encrypted-media"
                    allowFullScreen
                  />
                ) : (
                  // Placeholder for Render Link
                  <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center z-10 bg-gradient-to-b from-brand-bg to-brand-panel-light/20 select-none">
                    <div className="w-14 h-14 rounded-full bg-brand-panel border border-artlist-border flex items-center justify-center text-2xl mb-4 text-gray-500 shadow-lg">
                      📱
                    </div>
                    <h4 className="text-xs font-black text-gray-600 uppercase tracking-wider">
                      Ready for Capture
                    </h4>
                    <p className="text-[10px] text-gray-600 mt-1 font-semibold">
                      A sleek 9:16 portrait viewport will overlay the styled output here.
                    </p>
                  </div>
                )}

                {/* Subtle border shadow highlight inside */}
                <div className="absolute inset-0 border border-white/5 rounded-[28px] pointer-events-none z-30" />
              </div>

              {/* Download / Actions Panel */}
              <div className="w-full flex flex-col gap-3">
                {activeVideoFilename ? (
                  <a
                    href={`${BACKEND_URL}/api/download/${activeVideoFilename}`}
                    download
                    className="w-full bg-accent-neon hover:bg-accent-neon-hover text-black font-extrabold py-3.5 px-6 rounded-lg text-sm transition-all shadow-lg shadow-accent-neon/15 flex items-center justify-center gap-2 active:scale-95"
                  >
                    <Download className="w-4.5 h-4.5" />
                    Download Vertical Short
                  </a>
                ) : (
                  <button
                    disabled
                    className="w-full bg-brand-panel-light text-gray-500 border border-artlist-border font-bold py-3.5 px-6 rounded-lg text-sm transition-all flex items-center justify-center gap-2 cursor-not-allowed opacity-50"
                  >
                    <Lock className="w-4 h-4" />
                    Download Short (Render First)
                  </button>
                )}
                
                {activeClip && (
                  <div className="text-[10px] text-gray-500 font-semibold tracking-wide uppercase bg-brand-bg/40 border border-artlist-border/40 rounded p-2 text-left">
                    <span className="text-accent-amber block font-bold mb-0.5">Title Overlay Meta:</span>
                    Burn text: "{activeClip.title.toUpperCase()}"
                  </div>
                )}
              </div>

            </div>
          </div>

        </div>
      </section>

      {/* SUBSCRIPTION TIERS SECTION */}
      <section id="pricing-section" className="py-20 bg-artlist-dark border-t border-artlist-border">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-2xl sm:text-4xl font-extrabold text-white uppercase tracking-tight mb-3">
              Choose Your Subscription
            </h2>
            <p className="text-gray-400 text-sm max-w-lg mx-auto font-medium">
              Unlock unlimited AI renderings, auto-reframing quality, and custom subtitle burns styled for maximum viral impact.
            </p>
          </div>

          {/* Pricing Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            
            {/* FREE TIER */}
            <div className="bg-brand-panel border border-artlist-border rounded-2xl p-8 relative overflow-hidden flex flex-col justify-between group shadow-xl">
              <div>
                <div className="flex justify-between items-start mb-6">
                  <div>
                    <h3 className="text-lg font-black text-white uppercase tracking-wider">Free</h3>
                    <p className="text-xs text-gray-500 font-medium">Test drive HookFlow AI</p>
                  </div>
                  {subscription.plan === "Free" && (
                    <span className="bg-accent-neon/10 border border-accent-neon/20 text-accent-neon text-[10px] font-black px-2.5 py-1 rounded-full uppercase tracking-wider">
                      Current Plan
                    </span>
                  )}
                </div>

                <div className="mb-6 flex items-baseline gap-1">
                  <span className="text-4xl font-black text-white">$0</span>
                  <span className="text-xs text-gray-500 font-bold uppercase">/ forever</span>
                </div>

                <ul className="space-y-3.5 mb-8 text-xs font-semibold text-gray-400">
                  <li className="flex items-center gap-2.5">
                    <Check className="w-4 h-4 text-accent-neon shrink-0" />
                    <span>3 credits trial allocation</span>
                  </li>
                  <li className="flex items-center gap-2.5">
                    <Check className="w-4 h-4 text-accent-neon shrink-0" />
                    <span>720p maximum resolution</span>
                  </li>
                  <li className="flex items-center gap-2.5">
                    <Check className="w-4 h-4 text-accent-neon shrink-0" />
                    <span>Basic subtitle burns</span>
                  </li>
                  <li className="flex items-center gap-2.5 text-gray-600 line-through">
                    <X className="w-4 h-4 shrink-0" />
                    <span>Auto-Reframe AI tracking</span>
                  </li>
                  <li className="flex items-center gap-2.5 text-gray-600 line-through">
                    <X className="w-4 h-4 shrink-0" />
                    <span>Unlimited clip exports</span>
                  </li>
                </ul>
              </div>

              <button
                disabled
                className="w-full bg-brand-panel-light text-gray-500 border border-artlist-border font-bold py-3 px-4 rounded-lg text-xs tracking-wider uppercase opacity-50 cursor-not-allowed"
              >
                Default Account tier
              </button>
            </div>

            {/* CREATOR TIER */}
            <div className="bg-brand-panel border-2 border-accent-amber rounded-2xl p-8 relative overflow-hidden flex flex-col justify-between group shadow-2xl">
              {/* Popular Badge */}
              <div className="absolute top-0 right-0 bg-accent-amber text-black text-[9px] font-extrabold uppercase py-1 px-4 rounded-bl font-mono tracking-widest shadow">
                Most Popular
              </div>

              <div>
                <div className="flex justify-between items-start mb-6">
                  <div>
                    <h3 className="text-lg font-black text-white uppercase tracking-wider flex items-center gap-1.5">
                      Creator <Flame className="w-4 h-4 text-accent-amber fill-current" />
                    </h3>
                    <p className="text-xs text-gray-500 font-medium">For professional creators</p>
                  </div>
                  {subscription.plan === "Creator" && (
                    <span className="bg-accent-amber/15 border border-accent-amber/35 text-accent-amber text-[10px] font-black px-2.5 py-1 rounded-full uppercase tracking-wider">
                      Current Plan
                    </span>
                  )}
                </div>

                <div className="mb-6 flex items-baseline gap-1">
                  <span className="text-4xl font-black text-white">$19</span>
                  <span className="text-xs text-gray-500 font-bold uppercase">/ month</span>
                </div>

                <ul className="space-y-3.5 mb-8 text-xs font-semibold text-gray-300">
                  <li className="flex items-center gap-2.5">
                    <Check className="w-4 h-4 text-accent-amber shrink-0" />
                    <span className="text-white font-extrabold">60 credits monthly allocation</span>
                  </li>
                  <li className="flex items-center gap-2.5">
                    <Check className="w-4 h-4 text-accent-amber shrink-0" />
                    <span>1080p full HD rendering</span>
                  </li>
                  <li className="flex items-center gap-2.5">
                    <Check className="w-4 h-4 text-accent-amber shrink-0" />
                    <span>Auto-Reframe AI center focus</span>
                  </li>
                  <li className="flex items-center gap-2.5">
                    <Check className="w-4 h-4 text-accent-amber shrink-0" />
                    <span>AI subtitle templates</span>
                  </li>
                  <li className="flex items-center gap-2.5 text-gray-600 line-through">
                    <X className="w-4 h-4 shrink-0" />
                    <span>SRT transcript downloads</span>
                  </li>
                </ul>
              </div>

              <button
                onClick={() => triggerCheckout("Creator", 19.0)}
                disabled={subscription.plan === "Creator"}
                className={`w-full font-black py-3 px-4 rounded-lg text-xs tracking-wider uppercase transition-all shadow-md ${
                  subscription.plan === "Creator"
                    ? "bg-brand-panel-light text-gray-400 border border-artlist-border cursor-not-allowed"
                    : "bg-accent-amber hover:bg-accent-amber-hover text-black active:scale-95 hover:shadow-accent-amber/20"
                }`}
              >
                {subscription.plan === "Creator" ? "Active Subscription" : "Upgrade to Creator"}
              </button>
            </div>

            {/* PRO TIER */}
            <div className="bg-brand-panel border border-artlist-border rounded-2xl p-8 relative overflow-hidden flex flex-col justify-between group shadow-xl">
              <div>
                <div className="flex justify-between items-start mb-6">
                  <div>
                    <h3 className="text-lg font-black text-white uppercase tracking-wider flex items-center gap-1.5">
                      Pro <Zap className="w-4.5 h-4.5 text-accent-neon fill-current" />
                    </h3>
                    <p className="text-xs text-gray-500 font-medium">For agencies & studios</p>
                  </div>
                  {subscription.plan === "Pro" && (
                    <span className="bg-accent-neon/10 border border-accent-neon/20 text-accent-neon text-[10px] font-black px-2.5 py-1 rounded-full uppercase tracking-wider">
                      Current Plan
                    </span>
                  )}
                </div>

                <div className="mb-6 flex items-baseline gap-1">
                  <span className="text-4xl font-black text-white">$49</span>
                  <span className="text-xs text-gray-500 font-bold uppercase">/ month</span>
                </div>

                <ul className="space-y-3.5 mb-8 text-xs font-semibold text-gray-400">
                  <li className="flex items-center gap-2.5">
                    <Check className="w-4 h-4 text-accent-neon shrink-0" />
                    <span className="text-white font-extrabold">Unlimited clip exports</span>
                  </li>
                  <li className="flex items-center gap-2.5">
                    <Check className="w-4 h-4 text-accent-neon shrink-0" />
                    <span>Speed server rendering Priority</span>
                  </li>
                  <li className="flex items-center gap-2.5">
                    <Check className="w-4 h-4 text-accent-neon shrink-0" />
                    <span>Auto-Reframe AI + custom bounds</span>
                  </li>
                  <li className="flex items-center gap-2.5">
                    <Check className="w-4 h-4 text-accent-neon shrink-0" />
                    <span>Burned subtitle hooks + SRT transcripts</span>
                  </li>
                  <li className="flex items-center gap-2.5">
                    <Check className="w-4 h-4 text-accent-neon shrink-0" />
                    <span>API direct integrations</span>
                  </li>
                </ul>
              </div>

              <button
                onClick={() => triggerCheckout("Pro", 49.0)}
                disabled={subscription.plan === "Pro"}
                className={`w-full font-black py-3 px-4 rounded-lg text-xs tracking-wider uppercase transition-all shadow-md ${
                  subscription.plan === "Pro"
                    ? "bg-brand-panel-light text-gray-400 border border-artlist-border cursor-not-allowed"
                    : "bg-accent-neon hover:bg-accent-neon-hover text-black active:scale-95 hover:shadow-accent-neon/25"
                }`}
              >
                {subscription.plan === "Pro" ? "Active Subscription" : "Upgrade to Pro"}
              </button>
            </div>

          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="mt-auto bg-brand-bg border-t border-artlist-border/60 py-10 px-6 text-center text-xs font-semibold tracking-wider text-gray-500 uppercase">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            &copy; 2026 HOOKFLOW AI. ALL RIGHTS RESERVED. MOCK SANDBOX SIMULATOR.
          </div>
          <div className="flex gap-6">
            <a href="#hero-section" className="hover:text-white transition-colors">Privacy Policy</a>
            <a href="#hero-section" className="hover:text-white transition-colors">Terms of Service</a>
            <a href="#hero-section" className="hover:text-white transition-colors">Support Desk</a>
          </div>
        </div>
      </footer>

      {/* MOCK STRIPE CHECKOUT MODAL */}
      {checkoutPlan && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="relative w-full max-w-md bg-brand-panel border border-artlist-border rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-250">
            {/* Modal Header */}
            <div className="bg-brand-bg px-6 py-4 border-b border-artlist-border flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <CreditCard className="w-5 h-5 text-accent-neon" />
                <span className="font-extrabold text-sm text-white uppercase tracking-wider">
                  Stripe Payment Simulation
                </span>
              </div>
              <button
                onClick={() => setCheckoutPlan(null)}
                className="text-gray-400 hover:text-white rounded-full p-1 transition-all"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <form onSubmit={handleProcessPayment} className="p-6">
              <div className="mb-6 bg-brand-bg rounded-xl p-4 border border-artlist-border">
                <div className="flex items-center justify-between font-bold text-xs text-gray-400 uppercase mb-1.5">
                  <span>Selected Subscription</span>
                  <span className="text-accent-amber font-mono font-black">{checkoutPlan.name} Plan</span>
                </div>
                <div className="flex items-baseline justify-between">
                  <span className="text-xs text-gray-500 font-semibold uppercase">Total due now</span>
                  <span className="text-2xl font-black text-white font-mono">${checkoutPlan.price.toFixed(2)}</span>
                </div>
              </div>

              <div className="space-y-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-[10px] font-black text-gray-400 uppercase tracking-wider flex items-center gap-1">
                    <LockKeyhole className="w-3.5 h-3.5 text-accent-neon" />
                    Card Number (Simulation)
                  </label>
                  <input
                    type="text"
                    required
                    value={cardNumber}
                    onChange={(e) => setCardNumber(e.target.value)}
                    placeholder="4242 4242 4242 4242"
                    className="bg-brand-bg border border-artlist-border focus:border-accent-neon/80 rounded-lg p-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-accent-neon font-mono"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[10px] font-black text-gray-400 uppercase tracking-wider">
                      Expiration
                    </label>
                    <input
                      type="text"
                      required
                      value={cardExpiry}
                      onChange={(e) => setCardExpiry(e.target.value)}
                      placeholder="MM/YY"
                      className="bg-brand-bg border border-artlist-border focus:border-accent-neon/80 rounded-lg p-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-accent-neon font-mono text-center"
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[10px] font-black text-gray-400 uppercase tracking-wider">
                      CVC Code
                    </label>
                    <input
                      type="text"
                      required
                      value={cardCvc}
                      onChange={(e) => setCardCvc(e.target.value)}
                      placeholder="***"
                      className="bg-brand-bg border border-artlist-border focus:border-accent-neon/80 rounded-lg p-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-accent-neon font-mono text-center"
                    />
                  </div>
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="text-[10px] font-black text-gray-400 uppercase tracking-wider">
                    Cardholder Name
                  </label>
                  <input
                    type="text"
                    required
                    value={cardName}
                    onChange={(e) => setCardName(e.target.value)}
                    placeholder="e.g. John Doe"
                    className="bg-brand-bg border border-artlist-border focus:border-accent-neon/80 rounded-lg p-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-accent-neon"
                  />
                </div>
              </div>

              <div className="mt-8 flex flex-col gap-3">
                <button
                  type="submit"
                  disabled={isProcessingPayment}
                  className="w-full bg-accent-neon hover:bg-accent-neon-hover disabled:bg-brand-panel-light text-black font-black py-4 px-6 rounded-lg text-xs tracking-wider uppercase transition-all shadow-lg shadow-accent-neon/15 flex items-center justify-center gap-2 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isProcessingPayment ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin text-black" />
                      Securing transaction...
                    </>
                  ) : (
                    "Authorize simulated charge"
                  )}
                </button>
                <div className="text-[10px] text-center text-gray-500 font-semibold">
                  🛡️ SSL Secure Sandbox. No real currency is charged.
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* PAYMENT SUCCESS TOAST / MODAL */}
      {paymentSuccess && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-sm">
          <div className="w-full max-w-sm bg-brand-panel border border-accent-neon rounded-2xl p-8 text-center shadow-2xl relative overflow-hidden animate-in fade-in zoom-in duration-250">
            <div className="w-16 h-16 rounded-full bg-accent-neon/10 border-2 border-accent-neon text-accent-neon flex items-center justify-center text-3xl mx-auto mb-6 shadow-lg shadow-accent-neon/10">
              ✓
            </div>
            
            <h3 className="text-lg font-black text-white uppercase tracking-wider mb-2">
              Subscription Upgraded!
            </h3>
            
            <p className="text-xs text-gray-400 leading-relaxed font-semibold mb-6">
              Your mock billing transaction was approved successfully. HookFlow AI has unlocked your upgraded plan limits.
            </p>

            <button
              onClick={() => setPaymentSuccess(false)}
              className="bg-accent-neon hover:bg-accent-neon-hover text-black font-extrabold text-xs py-3 px-8 rounded-lg tracking-wider uppercase transition-all shadow-md active:scale-95"
            >
              Back to Studio
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
