// app/(auth)/onboard.tsx  — First-time Profile Studio wizard
import React, { useState } from "react";
import {
  View, Text, TouchableOpacity, ScrollView, TextInput,
  StyleSheet, SafeAreaView, Platform,
} from "react-native";
import { useRouter } from "expo-router";
import { C, R, S, USER_ID, API_BASE } from "../constants/config";
import { useAuth } from "../context/AuthContext";

type Step = 1|2|3|4|5|6; // 6 = summary

const MEMBER_ROLES = [
  {id:"adult-primary", emoji:"🧑", label:"Primary adult (you)"},
  {id:"adult-partner",  emoji:"🧑", label:"Partner / spouse"},
  {id:"child-young",    emoji:"👧", label:"Young child (under 8)"},
  {id:"child-teen",     emoji:"🧒", label:"Older child / teen"},
  {id:"parent-elder",   emoji:"👴", label:"Parent / elderly family"},
  {id:"pet",            emoji:"🐶", label:"Furry family member"},
];

const INTERESTS = [
  {id:"family-activities",emoji:"👨‍👩‍👧",label:"Family activities"},
  {id:"food-ideas",       emoji:"🍽️", label:"Food ideas"},
  {id:"home-projects",    emoji:"🏠",  label:"Home projects"},
  {id:"learning",         emoji:"📚",  label:"Learning"},
  {id:"wellness",         emoji:"🧘",  label:"Wellness"},
  {id:"local-outing",     emoji:"🗺️",  label:"Local outing"},
  {id:"entertainment",    emoji:"🎬",  label:"Entertainment"},
  {id:"games",            emoji:"🎮",  label:"Games"},
];

const LOCAL_OPTS = [
  {v:"5",  e:"🏘️", l:"Hyper local",  d:"Within 5 miles"},
  {v:"10", e:"🚶", l:"Local area",    d:"Up to 10 miles"},
  {v:"20", e:"🚗", l:"Nearby city",   d:"Up to 20 miles"},
  {v:"35", e:"🛣️", l:"Metro area",    d:"Up to 35 miles"},
];
const WEEKEND_OPTS = [
  {v:"30",  e:"🗺️", l:"Day trip",      d:"Up to 30 miles"},
  {v:"75",  e:"🏖️", l:"Short escape",  d:"Up to 75 miles"},
  {v:"150", e:"🛣️", l:"Road trip",     d:"Up to 150 miles"},
  {v:"300", e:"✈️", l:"Weekend away",  d:"150+ miles"},
];
const WEEKEND_STYLES = [
  {id:"adventure",emoji:"🏕️",label:"Adventurous",   desc:"Outdoors, exploring, new experiences"},
  {id:"social",   emoji:"🎉",label:"Social & lively", desc:"Dining out, friends, events"},
  {id:"relaxed",  emoji:"🛋️",label:"Relaxed & homey", desc:"Home time, movies, quiet activities"},
  {id:"mixed",    emoji:"🔄",label:"Mix it up",        desc:"Depends on the week"},
];
const PLAN_STYLES = [
  {id:"planner",     emoji:"📋",label:"Planned ahead", desc:"I like knowing in advance"},
  {id:"balanced",    emoji:"⚖️",label:"Balanced",      desc:"Some structure, some flexibility"},
  {id:"spontaneous", emoji:"⚡",label:"Spontaneous",   desc:"I prefer deciding on the day"},
];
const TONES = [
  {id:"executive",emoji:"💼",label:"Executive brief",  desc:"Concise, direct, data-first.",    ex:'"You have 3 events Saturday. Conflict at 2 PM."'},
  {id:"friendly", emoji:"😊",label:"Friendly coach",   desc:"Warm, encouraging, conversational.", ex:'"Hey! Busy Saturday — want me to fix that 2 PM clash?"'},
  {id:"balanced", emoji:"⚖️",label:"Balanced",         desc:"Professional but personable.",     ex:'"Heads up — scheduling conflict Saturday. Here\'s a fix."'},
];

const CITY_PRESETS = ["Tampa, FL","St. Petersburg, FL","Clearwater, FL","Orlando, FL"];

interface Profile {
  members:     string[];
  interests:   string[];
  city:        string;
  localRadius: string;
  weekendRadius:string;
  weekendStyle:string;
  planStyle:   string;
  tone:        string;
}

const DEFAULT: Profile = {
  members:[], interests:[], city:"Tampa, FL",
  localRadius:"20", weekendRadius:"75",
  weekendStyle:"", planStyle:"", tone:"",
};

// ── Helpers ───────────────────────────────────────────────────────────────────
function RadioCard({ selected, onPress, emoji, label, desc }: {
  selected:boolean; onPress:()=>void; emoji:string; label:string; desc?:string;
}) {
  return (
    <TouchableOpacity
      style={[st.radioCard, selected && st.radioCardSel]}
      onPress={onPress} activeOpacity={0.8}
    >
      <Text style={st.radioEmoji}>{emoji}</Text>
      <View style={{ flex:1 }}>
        <Text style={[st.radioLabel, selected && { color:C.acc }]}>{label}</Text>
        {desc && <Text style={st.radioDesc}>{desc}</Text>}
      </View>
      <View style={[st.radioCircle, selected && st.radioCircleSel]}>
        {selected && <View style={st.radioInner} />}
      </View>
    </TouchableOpacity>
  );
}

function SectionLabel({ text }: { text:string }) {
  return <Text style={st.sl}>{text}</Text>;
}

function ProgressDots({ step }: { step:number }) {
  return (
    <View style={st.progressRow}>
      {[1,2,3,4,5].map(i => (
        <View key={i} style={[
          st.progDot,
          i < step  && { backgroundColor:C.green, width:8 },
          i === step && { backgroundColor:C.acc, width:22 },
        ]} />
      ))}
    </View>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function OnboardScreen() {
  const router = useRouter();
  const { markOnboard } = useAuth();
  const [step, setStep] = useState<Step>(1);
  const [p, setP] = useState<Profile>({...DEFAULT});

  function toggle(key: keyof Profile, val: string) {
    const arr = p[key] as string[];
    setP(prev => ({
      ...prev,
      [key]: arr.includes(val) ? arr.filter(x => x!==val) : [...arr, val],
    }));
  }

  function set(key: keyof Profile, val: string) {
    setP(prev => ({ ...prev, [key]:val }));
  }

  function canNext(): boolean {
    if (step===1) return p.members.length > 0;
    if (step===2) return p.interests.length > 0;
    if (step===3) return p.city.length > 0;
    if (step===4) return p.weekendStyle !== "";
    if (step===5) return p.tone !== "";
    return true;
  }

  async function finish() {
    // Save profile to backend (best effort)
    try {
      await fetch(`${API_BASE}/api/memory/profile`, {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({ user_id:USER_ID, profile:p }),
      });
    } catch {}
    // markOnboard writes AsyncStorage AND updates AuthContext state
    // AuthGate in _layout.tsx detects auth="app" and redirects — no setTimeout needed
    await markOnboard();
  }

  // ── Splash ─────────────────────────────────────────────────────────────────
  if ((step as any) === 0) {
    return (
      <SafeAreaView style={st.safe}>
        <ScrollView contentContainerStyle={st.splashContent}>
          <View style={[st.splashLogo, S.md]}>
            <Text style={{ fontSize:38 }}>🏠</Text>
          </View>
          <Text style={st.splashTitle}>Welcome to Family COO</Text>
          <Text style={st.splashSub}>Your AI household executive assistant.{"\n"}Let's build your profile in 5 quick steps.</Text>
          <View style={{ marginTop:32, gap:14 }}>
            {[["🎯","Personalised suggestions","Outings, meals and plans tailored to your family"],["📅","Smart scheduling","Calendar insights based on how your family plans"],["🧠","AI that learns","The more you use it, the better it gets"],["🔒","Your data, your control","Update or reset anytime"]].map(([e,t,d])=>(
              <View key={t} style={st.splashFeature}>
                <View style={st.splashFeatureIcon}><Text style={{ fontSize:18 }}>{e}</Text></View>
                <View style={{ flex:1 }}>
                  <Text style={st.splashFTitle}>{t}</Text>
                  <Text style={st.splashFDesc}>{d}</Text>
                </View>
              </View>
            ))}
          </View>
          <TouchableOpacity style={[st.btnPrimary, S.sm, { marginTop:40 }]} onPress={() => setStep(1)}>
            <Text style={st.btnPrimaryText}>Build my profile — 5 steps</Text>
            <Text style={st.btnPrimarySubText}>Takes about 2 minutes</Text>
          </TouchableOpacity>
          <TouchableOpacity style={st.btnSkip} onPress={finish}>
            <Text style={st.btnSkipText}>Skip for now — set up later</Text>
          </TouchableOpacity>
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ── Summary ────────────────────────────────────────────────────────────────
  if (step === 6) {
    const memberLabels: Record<string,string> = {"adult-primary":"Primary adult","adult-partner":"Partner","child-young":"Young child","child-teen":"Older child","parent-elder":"Parent/elder","pet":"Furry member"};
    const interestLabels: Record<string,string> = {"family-activities":"Family activities","food-ideas":"Food ideas","home-projects":"Home projects","learning":"Learning","wellness":"Wellness","local-outing":"Local outing","entertainment":"Entertainment","games":"Games"};
    const toneLabel: Record<string,string> = {executive:"Executive brief",friendly:"Friendly coach",balanced:"Balanced"};
    const weekendLabel: Record<string,string> = {adventure:"Adventurous",social:"Social & lively",relaxed:"Relaxed & homey",mixed:"Mix it up"};
    const planLabel: Record<string,string> = {planner:"Planned ahead",balanced:"Balanced",spontaneous:"Spontaneous"};
    const lrLabel: Record<string,string> = {"5":"Within 5 mi","10":"Up to 10 mi","20":"Up to 20 mi","35":"Up to 35 mi"};
    const wrLabel: Record<string,string> = {"30":"Day trip (30 mi)","75":"Short escape (75 mi)","150":"Road trip (150 mi)","300":"Weekend away"};

    const sections = [
      {n:1 as Step, emoji:"👨‍👩‍👧", title:"Household",    items:p.members.map(m=>memberLabels[m]||m)},
      {n:2 as Step, emoji:"🌟",       title:"Lifestyle",    items:p.interests.map(i=>interestLabels[i]||i)},
      {n:3 as Step, emoji:"🗺️",       title:"Local world",  items:[p.city, lrLabel[p.localRadius], wrLabel[p.weekendRadius]].filter(Boolean)},
      {n:4 as Step, emoji:"📅",       title:"Style",        items:[weekendLabel[p.weekendStyle], planLabel[p.planStyle]].filter(Boolean)},
      {n:5 as Step, emoji:"🎙️",       title:"Tone",         items:[toneLabel[p.tone]].filter(Boolean)},
    ];

    return (
      <SafeAreaView style={st.safe}>
        <View style={st.successHeader}>
          <Text style={{ fontSize:36, marginBottom:12 }}>✅</Text>
          <Text style={st.successTitle}>Profile built!</Text>
          <Text style={st.successSub}>Family COO is now personalised for your household.</Text>
        </View>
        <ScrollView contentContainerStyle={{ padding:16, paddingBottom:40 }}>
          <SectionLabel text="YOUR PROFILE SUMMARY" />
          {sections.map(s => (
            <View key={s.title} style={[st.summaryCard, S.xs]}>
              <View style={st.summaryHeader}>
                <Text style={{ fontSize:18 }}>{s.emoji}</Text>
                <Text style={st.summaryTitle}>{s.title}</Text>
                <TouchableOpacity onPress={() => setStep(s.n)}>
                  <Text style={st.summaryEdit}>Edit</Text>
                </TouchableOpacity>
              </View>
              <View style={st.pillRow}>
                {s.items.length > 0
                  ? s.items.map(i => <View key={i} style={st.pill}><Text style={st.pillText}>{i}</Text></View>)
                  : <Text style={{ fontSize:12, color:C.ink3 }}>Not set</Text>
                }
              </View>
            </View>
          ))}
          <View style={[st.noteCard, { marginTop:4 }]}>
            <Text style={st.noteText}>✏️ Update anytime in Engine tab → Profile Studio.</Text>
          </View>
          <TouchableOpacity style={[st.btnPrimary, S.sm, { marginTop:16 }]} onPress={finish}>
            <Text style={st.btnPrimaryText}>Take me to my Briefing →</Text>
          </TouchableOpacity>
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ── Steps 1–5 ──────────────────────────────────────────────────────────────
  const stepConfigs = [
    {emoji:"👨‍👩‍👧", title:"Your household",        sub:"Tell us who's in your home."},
    {emoji:"🌟",      title:"Lifestyle & interests", sub:"What does your household enjoy?"},
    {emoji:"🗺️",      title:"Your local world",      sub:"Where you're based and how far you like to venture."},
    {emoji:"📅",      title:"Weekend & planning",    sub:"How your family likes to spend free time."},
    {emoji:"🎙️",      title:"Assistant tone",        sub:"How should Family COO communicate with you?"},
  ];
  const cfg = stepConfigs[step-1];

  return (
    <SafeAreaView style={st.safe}>
      {/* Step header */}
      <View style={st.stepHeader}>
        <View style={st.stepHeaderTop}>
          {step > 1
            ? <TouchableOpacity onPress={() => setStep((step-1) as Step)} style={st.backBtn}>
                <Text style={st.backArrow}>←</Text>
              </TouchableOpacity>
            : <View style={{ width:36 }} />
          }
          <ProgressDots step={step} />
          <View style={st.stepNum}>
            <Text style={st.stepNumText}>{step}/5</Text>
          </View>
        </View>
        <View style={{ flexDirection:"row", alignItems:"center", gap:10, marginTop:8 }}>
          <Text style={{ fontSize:28 }}>{cfg.emoji}</Text>
          <View>
            <Text style={st.stepTitle}>{cfg.title}</Text>
            <Text style={st.stepSub}>{cfg.sub}</Text>
          </View>
        </View>
      </View>

      <ScrollView contentContainerStyle={st.stepContent}>
        {/* ── STEP 1 ── */}
        {step===1 && (
          <>
            <SectionLabel text="WHO'S IN YOUR HOUSEHOLD?" />
            {MEMBER_ROLES.map(r => (
              <TouchableOpacity key={r.id}
                style={[st.memberRow, p.members.includes(r.id) && st.memberRowSel]}
                onPress={() => toggle("members", r.id)} activeOpacity={0.8}>
                <Text style={{ fontSize:20 }}>{r.emoji}</Text>
                <Text style={[st.memberLabel, p.members.includes(r.id) && { color:C.acc, fontWeight:"700" }]}>{r.label}</Text>
                <View style={[st.radioCircle, p.members.includes(r.id) && st.radioCircleSel]}>
                  {p.members.includes(r.id) && <View style={st.radioInner} />}
                </View>
              </TouchableOpacity>
            ))}
            <View style={st.noteCard}>
              <Text style={st.noteText}>💡 Helps suggest kid-friendly outings, family meal ideas, and plan around everyone's schedule.</Text>
            </View>
          </>
        )}

        {/* ── STEP 2 ── */}
        {step===2 && (
          <>
            <SectionLabel text="WHAT DOES YOUR HOUSEHOLD ENJOY?" />
            <Text style={st.stepHint}>Select everything that applies — more = better suggestions.</Text>
            <View style={st.interestGrid}>
              {INTERESTS.map(item => {
                const sel = p.interests.includes(item.id);
                return (
                  <TouchableOpacity key={item.id}
                    style={[st.interestCard, sel && st.interestCardSel]}
                    onPress={() => toggle("interests", item.id)} activeOpacity={0.8}>
                    <Text style={{ fontSize:22, marginBottom:5 }}>{item.emoji}</Text>
                    <Text style={[st.interestLabel, sel && { color:C.acc, fontWeight:"700" }]}>{item.label}</Text>
                    {sel && <View style={st.interestCheck}><Text style={{ fontSize:10, color:"#fff" }}>✓</Text></View>}
                  </TouchableOpacity>
                );
              })}
            </View>
            <View style={[st.noteCard, { borderColor:C.border }]}>
              <Text style={[st.noteText, { color:C.acc }]}>
                {p.interests.length === 0
                  ? "Pick at least one area to get started."
                  : p.interests.length <= 2
                  ? `${p.interests.length} selected — pick more for richer suggestions.`
                  : `${p.interests.length} interests selected — great personalisation!`}
              </Text>
            </View>
          </>
        )}

        {/* ── STEP 3 ── */}
        {step===3 && (
          <>
            <SectionLabel text="YOUR HOME BASE" />
            <TextInput
              style={st.cityInput}
              value={p.city}
              onChangeText={v => set("city", v)}
              placeholder="e.g. Tampa, FL"
              placeholderTextColor={C.ink3}
            />
            <View style={st.cityPresets}>
              {CITY_PRESETS.map(c => (
                <TouchableOpacity key={c} onPress={() => set("city", c)}
                  style={[st.presetChip, p.city===c && st.presetChipSel]}>
                  <Text style={[st.presetText, p.city===c && { color:C.acc }]}>{c}</Text>
                </TouchableOpacity>
              ))}
            </View>

            <View style={st.divider} />
            <SectionLabel text="🏘️ LOCAL TRAVEL" />
            <Text style={st.stepHint}>For everyday outings, errands and activities.</Text>
            {LOCAL_OPTS.map(o => (
              <RadioCard key={o.v}
                selected={p.localRadius===o.v}
                onPress={() => set("localRadius", o.v)}
                emoji={o.e} label={o.l} desc={o.d} />
            ))}

            <View style={st.divider} />
            <SectionLabel text="🏖️ WEEKEND TRAVEL" />
            <Text style={st.stepHint}>How far for weekend plans?</Text>
            {WEEKEND_OPTS.map(o => (
              <RadioCard key={o.v}
                selected={p.weekendRadius===o.v}
                onPress={() => set("weekendRadius", o.v)}
                emoji={o.e} label={o.l} desc={o.d} />
            ))}
          </>
        )}

        {/* ── STEP 4 ── */}
        {step===4 && (
          <>
            <SectionLabel text="WEEKEND VIBE" />
            {WEEKEND_STYLES.map(w => (
              <RadioCard key={w.id}
                selected={p.weekendStyle===w.id}
                onPress={() => set("weekendStyle", w.id)}
                emoji={w.emoji} label={w.label} desc={w.desc} />
            ))}
            <View style={st.divider} />
            <SectionLabel text="PLANNING STYLE" />
            {PLAN_STYLES.map(ps => (
              <RadioCard key={ps.id}
                selected={p.planStyle===ps.id}
                onPress={() => set("planStyle", ps.id)}
                emoji={ps.emoji} label={ps.label} desc={ps.desc} />
            ))}
          </>
        )}

        {/* ── STEP 5 ── */}
        {step===5 && (
          <>
            {TONES.map(t => (
              <TouchableOpacity key={t.id}
                style={[st.toneCard, p.tone===t.id && st.toneCardSel]}
                onPress={() => set("tone", t.id)} activeOpacity={0.85}>
                <View style={st.toneTop}>
                  <Text style={{ fontSize:22 }}>{t.emoji}</Text>
                  <View style={{ flex:1 }}>
                    <Text style={[st.toneLabel, p.tone===t.id && { color:C.acc }]}>{t.label}</Text>
                    <Text style={st.toneDesc}>{t.desc}</Text>
                  </View>
                  <View style={[st.radioCircle, p.tone===t.id && st.radioCircleSel]}>
                    {p.tone===t.id && <View style={st.radioInner} />}
                  </View>
                </View>
                <View style={[st.exampleBox, p.tone===t.id && { borderLeftColor:C.acc, backgroundColor:C.soft }]}>
                  <Text style={st.exampleLabel}>EXAMPLE</Text>
                  <Text style={[st.exampleText, p.tone===t.id && { color:C.acc }]}>{t.ex}</Text>
                </View>
              </TouchableOpacity>
            ))}
          </>
        )}

        <View style={{ height:100 }} />
      </ScrollView>

      {/* Footer CTA */}
      <View style={st.footer}>
        <TouchableOpacity
          style={[st.btnPrimary, !canNext() && st.btnPrimaryDis]}
          disabled={!canNext()}
          onPress={() => step < 5 ? setStep((step+1) as Step) : setStep(6)}
          activeOpacity={0.85}
        >
          <Text style={[st.btnPrimaryText, !canNext() && { color:C.ink3 }]}>
            {step < 5 ? "Continue →" : "Finish setup ✓"}
          </Text>
        </TouchableOpacity>
        {step < 5 && (
          <TouchableOpacity onPress={() => setStep((step+1) as Step)}>
            <Text style={st.btnSkipText}>Skip this step</Text>
          </TouchableOpacity>
        )}
      </View>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  safe:        { flex:1, backgroundColor:C.bg },
  // Splash
  splashContent:   { padding:28, paddingTop:56, alignItems:"center" },
  splashLogo:      { width:80, height:80, borderRadius:22, backgroundColor:C.acc2, alignItems:"center", justifyContent:"center", marginBottom:20 },
  splashTitle:     { fontSize:26, fontWeight:"800", color:C.ink, marginBottom:8 },
  splashSub:       { fontSize:14, color:C.ink2, textAlign:"center", lineHeight:21, marginBottom:4 },
  splashFeature:   { flexDirection:"row", gap:12, width:"100%" },
  splashFeatureIcon:{ width:38, height:38, borderRadius:10, backgroundColor:C.soft, alignItems:"center", justifyContent:"center", flexShrink:0 },
  splashFTitle:    { fontSize:13, fontWeight:"700", color:C.ink },
  splashFDesc:     { fontSize:12, color:C.ink2, marginTop:2 },
  // Summary
  successHeader:   { backgroundColor:C.acc2, padding:28, alignItems:"center" },
  successTitle:    { fontSize:22, fontWeight:"800", color:"#fff", marginBottom:6 },
  successSub:      { fontSize:13, color:"rgba(255,255,255,0.8)", textAlign:"center" },
  summaryCard:     { backgroundColor:C.bgCard, borderRadius:R.lg, borderWidth:0.5, borderColor:C.border2, padding:13, marginBottom:10 },
  summaryHeader:   { flexDirection:"row", alignItems:"center", gap:8, marginBottom:8 },
  summaryTitle:    { flex:1, fontSize:12, fontWeight:"700", color:C.ink },
  summaryEdit:     { fontSize:11, fontWeight:"700", color:C.acc },
  pillRow:         { flexDirection:"row", flexWrap:"wrap", gap:6 },
  pill:            { backgroundColor:C.bg2, borderRadius:R.full, paddingHorizontal:10, paddingVertical:4 },
  pillText:        { fontSize:12, color:C.ink2, fontWeight:"500" },
  // Step header
  stepHeader:      { backgroundColor:C.bgCard, borderBottomWidth:0.5, borderBottomColor:C.border2, padding:14, paddingBottom:14 },
  stepHeaderTop:   { flexDirection:"row", alignItems:"center", justifyContent:"space-between", marginBottom:8 },
  backBtn:         { width:36, height:36, borderRadius:R.sm, backgroundColor:C.soft, alignItems:"center", justifyContent:"center" },
  backArrow:       { fontSize:18, color:C.acc },
  progressRow:     { flexDirection:"row", gap:6, alignItems:"center" },
  progDot:         { width:8, height:8, borderRadius:4, backgroundColor:C.border, transition:"all 0.2s" } as any,
  stepNum:         { width:36, height:36, borderRadius:R.sm, backgroundColor:C.soft, alignItems:"center", justifyContent:"center" },
  stepNumText:     { fontSize:11, fontWeight:"700", color:C.acc },
  stepTitle:       { fontSize:17, fontWeight:"800", color:C.ink },
  stepSub:         { fontSize:12, color:C.ink2, marginTop:2 },
  stepContent:     { padding:16, paddingBottom:120 },
  stepHint:        { fontSize:12, color:C.ink3, marginBottom:12, marginTop:-4 },
  // Step 1 members
  memberRow:       { flexDirection:"row", alignItems:"center", gap:12, padding:12, borderRadius:R.lg, borderWidth:1.5, borderColor:C.border2, backgroundColor:C.bgCard, marginBottom:8 },
  memberRowSel:    { borderColor:C.acc, backgroundColor:C.soft },
  memberLabel:     { flex:1, fontSize:14, fontWeight:"500", color:C.ink },
  // Step 2 interests
  interestGrid:    { flexDirection:"row", flexWrap:"wrap", gap:10, marginBottom:14 },
  interestCard:    { width:"47%", borderRadius:R.lg, borderWidth:1.5, borderColor:C.border2, backgroundColor:C.bgCard, padding:13, alignItems:"flex-start", position:"relative" },
  interestCardSel: { borderColor:C.acc, backgroundColor:C.soft },
  interestLabel:   { fontSize:13, fontWeight:"600", color:C.ink },
  interestCheck:   { position:"absolute", top:8, right:8, width:18, height:18, borderRadius:9, backgroundColor:C.acc, alignItems:"center", justifyContent:"center" },
  // Step 3 city
  cityInput:       { borderWidth:1.5, borderColor:C.border2, borderRadius:R.lg, padding:12, fontSize:14, color:C.ink, backgroundColor:C.bgCard, marginBottom:10 },
  cityPresets:     { flexDirection:"row", flexWrap:"wrap", gap:7, marginBottom:6 },
  presetChip:      { paddingHorizontal:12, paddingVertical:6, borderRadius:R.full, borderWidth:1, borderColor:C.border2, backgroundColor:C.bgCard },
  presetChipSel:   { borderColor:C.acc, backgroundColor:C.soft },
  presetText:      { fontSize:12, color:C.ink2, fontWeight:"600" },
  divider:         { height:1, backgroundColor:C.border2, marginVertical:18 },
  // Radio card
  radioCard:       { flexDirection:"row", alignItems:"center", gap:12, padding:12, borderRadius:R.lg, borderWidth:1.5, borderColor:C.border2, backgroundColor:C.bgCard, marginBottom:8 },
  radioCardSel:    { borderColor:C.acc, backgroundColor:C.soft },
  radioEmoji:      { fontSize:20 },
  radioLabel:      { fontSize:13, fontWeight:"600", color:C.ink },
  radioDesc:       { fontSize:11, color:C.ink3, marginTop:2 },
  radioCircle:     { width:18, height:18, borderRadius:9, borderWidth:1.5, borderColor:C.border, backgroundColor:"transparent", alignItems:"center", justifyContent:"center" },
  radioCircleSel:  { borderColor:C.acc, backgroundColor:C.acc },
  radioInner:      { width:6, height:6, borderRadius:3, backgroundColor:"#fff" },
  // Step 5 tone
  toneCard:        { borderWidth:1.5, borderColor:C.border2, borderRadius:R.xl, padding:14, backgroundColor:C.bgCard, marginBottom:10 },
  toneCardSel:     { borderColor:C.acc, backgroundColor:C.soft },
  toneTop:         { flexDirection:"row", alignItems:"center", gap:10, marginBottom:8 },
  toneLabel:       { fontSize:14, fontWeight:"700", color:C.ink },
  toneDesc:        { fontSize:12, color:C.ink2, marginTop:1 },
  exampleBox:      { backgroundColor:C.bg, borderRadius:R.sm, padding:9, borderLeftWidth:3, borderLeftColor:C.border2 },
  exampleLabel:    { fontSize:10, fontWeight:"700", color:C.ink3, marginBottom:3 },
  exampleText:     { fontSize:12, color:C.ink2, lineHeight:18, fontStyle:"italic" },
  // Shared
  sl:            { fontSize:10, fontWeight:"700", color:C.ink3, letterSpacing:1.2, marginBottom:10 },
  noteCard:      { backgroundColor:C.amberS, borderRadius:R.md, borderWidth:0.5, borderColor:C.amberB, padding:11, marginTop:4 },
  noteText:      { fontSize:12, color:"#78350F", lineHeight:18 },
  footer:        { position:"absolute", bottom:0, left:0, right:0, backgroundColor:C.bgCard, borderTopWidth:0.5, borderTopColor:C.border2, padding:16, paddingBottom:Platform.OS==="ios"?32:16, gap:8 },
  btnPrimary:    { backgroundColor:C.acc2, borderRadius:R.lg, padding:15, alignItems:"center" },
  btnPrimaryDis: { backgroundColor:C.border2 },
  btnPrimaryText:{ fontSize:15, fontWeight:"700", color:"#fff" },
  btnPrimarySubText:{ fontSize:11, color:"rgba(255,255,255,0.75)", marginTop:2 },
  btnSkip:       { alignItems:"center", padding:10 },
  btnSkipText:   { fontSize:13, color:C.ink3, fontWeight:"600" },
});
