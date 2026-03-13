// app/(tabs)/_layout.tsx  — Briefing → Chat → Calendar → Missions → Engine
import { Tabs } from "expo-router";
import { Platform, View, StyleSheet, Text } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { C, R } from "../constants/config";

type IName = React.ComponentProps<typeof Ionicons>["name"];

function TabIcon({ name, focused }: { name: IName; focused: boolean }) {
  return (
    <View style={[st.icon, focused && st.iconActive]}>
      <Ionicons name={name} size={Platform.OS === "web" ? 16 : 21}
        color={focused ? C.indigo : C.inkMuted} />
    </View>
  );
}

function HeroChatIcon({ focused }: { focused: boolean }) {
  if (Platform.OS === "web") {
    return (
      <View style={[st.icon, focused && st.iconActive]}>
        <Ionicons name="chatbubble" size={16} color={focused ? C.indigo : C.inkMuted} />
      </View>
    );
  }
  return (
    <View style={st.heroWrap}>
      <View style={[st.heroBtn, focused && st.heroBtnActive]}>
        <Ionicons name="chatbubble" size={22} color={focused ? "#fff" : C.inkSub} />
      </View>
    </View>
  );
}

// ORDER: Briefing → Chat (hero) → Calendar → Missions → Engine
const TABS: Array<{ name:string; title:string; icon:IName; iconOff:IName; hero?:boolean }> = [
  { name:"index",    title:"Briefing", icon:"grid",             iconOff:"grid-outline"             },
  { name:"chat",     title:"Chat",     icon:"chatbubble",       iconOff:"chatbubble-outline", hero:true },
  { name:"calendar", title:"Calendar", icon:"calendar",         iconOff:"calendar-outline"         },
  { name:"missions", title:"Missions", icon:"checkmark-circle", iconOff:"checkmark-circle-outline" },
  { name:"settings", title:"Engine",   icon:"cpu",              iconOff:"cpu-outline"              },
];

export default function TabsLayout() {
  const web = Platform.OS === "web";
  return (
    <Tabs screenOptions={{
      headerShown:             false,
      tabBarStyle:             web ? st.webBar : st.mobileBar,
      tabBarActiveTintColor:   C.indigo,
      tabBarInactiveTintColor: C.inkMuted,
      tabBarLabelStyle:        web ? st.webLabel : st.mobileLabel,
      tabBarItemStyle:         web ? st.webItem  : undefined,
    }}>
      {TABS.map(({ name, title, icon, iconOff, hero }) => (
        <Tabs.Screen key={name} name={name} options={{
          title,
          tabBarLabel: ({ focused }) =>
            hero && !web
              ? <Text style={[st.heroLabel, focused && st.heroLabelActive]}>Chat</Text>
              : undefined,
          tabBarIcon: ({ focused }) =>
            hero
              ? <HeroChatIcon focused={focused} />
              : <TabIcon name={focused ? icon : iconOff} focused={focused} />,
        }} />
      ))}
    </Tabs>
  );
}

const st = StyleSheet.create({
  webBar: {
    backgroundColor:C.bgCard, height:52,
    borderBottomWidth:1, borderBottomColor:C.border, borderTopWidth:0,
    shadowColor:"#0F172A", shadowOffset:{width:0,height:1}, shadowOpacity:0.06, shadowRadius:4, elevation:2,
  },
  webItem:  { flexDirection:"row", alignItems:"center", justifyContent:"center", paddingHorizontal:12 },
  webLabel: { fontSize:11, fontWeight:"700", marginTop:0 },
  mobileBar: {
    backgroundColor:C.bgCard, borderTopColor:C.border, borderTopWidth:1,
    height: Platform.OS === "ios" ? 88 : 68,
    paddingBottom: Platform.OS === "ios" ? 28 : 10,
    paddingTop:8,
    shadowColor:"#0F172A", shadowOffset:{width:0,height:-2}, shadowOpacity:0.07, shadowRadius:8, elevation:10,
  },
  mobileLabel:      { fontSize:10, fontWeight:"700", marginTop:2 },
  icon:             { width:Platform.OS==="web"?28:36, height:Platform.OS==="web"?28:36, borderRadius:R.sm, alignItems:"center", justifyContent:"center" },
  iconActive:       { backgroundColor:C.indigoSoft },
  heroWrap:         { alignItems:"center", justifyContent:"flex-end", height:60, marginTop:-20 },
  heroBtn:          { width:56, height:56, borderRadius:28, backgroundColor:C.bgInput, alignItems:"center", justifyContent:"center", shadowColor:C.indigo, shadowOffset:{width:0,height:4}, shadowOpacity:0.2, shadowRadius:8, elevation:6, borderWidth:1, borderColor:C.border },
  heroBtnActive:    { backgroundColor:C.indigo, borderColor:C.indigoDark, shadowOpacity:0.35 },
  heroLabel:        { fontSize:10, fontWeight:"700", color:C.inkMuted, marginTop:2 },
  heroLabelActive:  { color:C.indigo },
});
