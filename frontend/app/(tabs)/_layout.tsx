// app/(tabs)/_layout.tsx  — Lavender theme tab bar
import { Tabs } from "expo-router";
import { Platform, View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { C, R, USER_ID } from "../constants/config";

type IName = React.ComponentProps<typeof Ionicons>["name"];

function TabIcon({ name, focused }: { name:IName; focused:boolean }) {
  return (
    <View style={[st.icon, focused && st.iconActive]}>
      <Ionicons name={name} size={Platform.OS==="web"?16:21}
        color={focused ? C.acc : C.ink3} />
    </View>
  );
}

function HeroChatIcon({ focused }: { focused:boolean }) {
  if (Platform.OS === "web") {
    return (
      <View style={[st.icon, focused && st.iconActive]}>
        <Ionicons name="chatbubble" size={16} color={focused ? C.acc : C.ink3} />
      </View>
    );
  }
  return (
    <View style={st.heroWrap}>
      <View style={[st.heroBtn, focused && st.heroBtnActive]}>
        <Ionicons name="chatbubble" size={22} color={focused ? "#fff" : C.ink3} />
      </View>
    </View>
  );
}

const TABS: Array<{name:string;title:string;icon:IName;iconOff:IName;hero?:boolean}> = [
  {name:"index",    title:"Briefing", icon:"grid",             iconOff:"grid-outline"},
  {name:"chat",     title:"Chat",     icon:"chatbubble",       iconOff:"chatbubble-outline", hero:true},
  {name:"calendar", title:"Calendar", icon:"calendar",         iconOff:"calendar-outline"},
  {name:"missions", title:"Missions", icon:"checkmark-circle", iconOff:"checkmark-circle-outline"},
  {name:"settings", title:"Engine",   icon:"cpu",              iconOff:"cpu-outline"},
  {name:"admin",    title:"Admin",    icon:"shield",           iconOff:"shield-outline"},
];

// Admin-only emails — tab bar button is hidden for all other users
const ADMIN_EMAILS = ["tushar.khandare@gmail.com"];

export default function TabsLayout() {
  const web = Platform.OS === "web";
  return (
    <Tabs screenOptions={{
      headerShown:             false,
      tabBarStyle:             web ? st.webBar : st.mobileBar,
      tabBarActiveTintColor:   C.acc,
      tabBarInactiveTintColor: C.ink3,
      tabBarLabelStyle:        web ? st.webLabel : st.mobileLabel,
      tabBarItemStyle:         web ? st.webItem  : undefined,
    }}>
      {TABS.map(({name,title,icon,iconOff,hero}) => (
        <Tabs.Screen key={name} name={name} options={{
          title,
          // Hide admin tab from non-admin users — route still navigable via long-press
          tabBarButton: name === "admin" && !ADMIN_EMAILS.includes(USER_ID)
            ? () => null
            : undefined,
          tabBarLabel: ({focused}) =>
            hero && !web
              ? <Text style={[st.heroLabel, focused && st.heroLabelActive]}>Chat</Text>
              : undefined,
          tabBarIcon: ({focused}) =>
            hero
              ? <HeroChatIcon focused={focused} />
              : <TabIcon name={focused?icon:iconOff} focused={focused} />,
        }} />
      ))}
    </Tabs>
  );
}

const st = StyleSheet.create({
  webBar: {
    backgroundColor:C.bgCard, height:52,
    borderBottomWidth:0.5, borderBottomColor:C.border2, borderTopWidth:0,
    shadowColor:"#6D28D9", shadowOffset:{width:0,height:1}, shadowOpacity:0.06, shadowRadius:4, elevation:2,
  },
  webItem:  { flexDirection:"row", alignItems:"center", justifyContent:"center", paddingHorizontal:12 },
  webLabel: { fontSize:11, fontWeight:"700", marginTop:0 },
  mobileBar: {
    backgroundColor:C.bgCard,
    borderTopColor:C.border2, borderTopWidth:0.5,
    height: Platform.OS==="ios" ? 88 : 68,
    paddingBottom: Platform.OS==="ios" ? 28 : 10,
    paddingTop:8,
    shadowColor:"#6D28D9", shadowOffset:{width:0,height:-2}, shadowOpacity:0.06, shadowRadius:8, elevation:8,
  },
  mobileLabel:     { fontSize:10, fontWeight:"700", marginTop:2 },
  icon:            { width:Platform.OS==="web"?28:36, height:Platform.OS==="web"?28:36, borderRadius:R.sm, alignItems:"center", justifyContent:"center" },
  iconActive:      { backgroundColor:C.soft },
  heroWrap:        { alignItems:"center", justifyContent:"flex-end", height:60, marginTop:-20 },
  heroBtn:         { width:56, height:56, borderRadius:28, backgroundColor:C.bg2, alignItems:"center", justifyContent:"center", shadowColor:C.acc, shadowOffset:{width:0,height:4}, shadowOpacity:0.18, shadowRadius:8, elevation:6, borderWidth:0.5, borderColor:C.border2 },
  heroBtnActive:   { backgroundColor:C.acc2, borderColor:C.acc, shadowOpacity:0.3 },
  heroLabel:       { fontSize:10, fontWeight:"700", color:C.ink3, marginTop:2 },
  heroLabelActive: { color:C.acc },
});
