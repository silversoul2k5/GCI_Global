import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { checkHealth, fetchCustomer, fetchDemoCustomers } from '../api';
import { COMMON_API_BASES, FALLBACK_DEMO_CUSTOMER_IDS, useAppConfig } from '../config';

export default function HomeScreen() {
  const { apiBase, setApiBase, customerId, setCustomerId } = useAppConfig();
  const [draftApiBase, setDraftApiBase] = useState(apiBase);
  const [connection, setConnection] = useState('checking'); // checking | ok | down
  const [customer, setCustomer] = useState(null);
  const [demoIds, setDemoIds] = useState(FALLBACK_DEMO_CUSTOMER_IDS);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setError(null);

    const normalizedBase = apiBase.trim();
    const candidateBases = Array.from(new Set([normalizedBase, ...COMMON_API_BASES].filter(Boolean)));
    let activeBase = normalizedBase;
    let lastError = null;

    for (const candidate of candidateBases) {
      try {
        await checkHealth(candidate);
        activeBase = candidate;
        break;
      } catch (e) {
        lastError = e.message;
      }
    }

    if (!activeBase) {
      setConnection('down');
      setError(lastError || 'Could not reach the server.');
      return;
    }

    if (activeBase !== normalizedBase) {
      setApiBase(activeBase);
      setDraftApiBase(activeBase);
    }

    setConnection('ok');
    setLoading(true);
    try {
      const [c, demoList] = await Promise.all([
        fetchCustomer(activeBase, customerId),
        fetchDemoCustomers(activeBase, 5).catch(() => null),
      ]);
      setCustomer(c);
      if (demoList?.customers?.length) {
        setDemoIds(demoList.customers.map((x) => x.customer_id));
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [apiBase, customerId, setApiBase]);

  useEffect(() => {
    load();
  }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const saveApiBase = () => {
    setApiBase(draftApiBase.trim());
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        <View style={styles.headerRow}>
          <View style={styles.logoMark}>
            <Text style={styles.logoMarkText}>S</Text>
          </View>
          <View>
            <Text style={styles.brand}>Signal Mobile</Text>
            <Text style={styles.brandSub}>Your account</Text>
          </View>
          <View style={{ flex: 1 }} />
          <View style={[styles.statusDot, connection === 'ok' ? styles.dotOk : connection === 'down' ? styles.dotDown : styles.dotChecking]} />
        </View>

        {connection === 'down' && (
          <View style={styles.errorBanner}>
            <Text style={styles.errorTitle}>Can't reach the server</Text>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}

        <View style={styles.card}>
          <Text style={styles.cardLabel}>Signed in as</Text>
          {loading && !customer ? (
            <ActivityIndicator style={{ marginVertical: 12 }} />
          ) : customer ? (
            <>
              <Text style={styles.customerName}>Customer #{customer.customer_id}</Text>
              <View style={styles.statRow}>
                <View style={styles.statBox}>
                  <Text style={styles.statValue}>{customer.months ?? '—'}</Text>
                  <Text style={styles.statLabel}>months with us</Text>
                </View>
                <View style={styles.statBox}>
                  <Text style={styles.statValue}>${customer.avgrev?.toFixed(0) ?? '—'}</Text>
                  <Text style={styles.statLabel}>avg. monthly bill</Text>
                </View>
                <View style={styles.statBox}>
                  <Text style={styles.statValue}>{customer.avgmou ? Math.round(customer.avgmou) : '—'}</Text>
                  <Text style={styles.statLabel}>avg. minutes/mo</Text>
                </View>
              </View>
            </>
          ) : (
            <Text style={styles.brandSub}>No account loaded.</Text>
          )}
        </View>

        <Text style={styles.sectionTitle}>Demo: switch account</Text>
        <Text style={styles.sectionHint}>
          This app represents a customer's phone. Switch between a few real accounts from the
          dataset to test sending yourself different offers from the company website.
        </Text>
        <View style={styles.pillRow}>
          {demoIds.map((id) => (
            <Pressable
              key={id}
              onPress={() => setCustomerId(id)}
              style={[styles.pill, id === customerId && styles.pillActive]}
            >
              <Text style={[styles.pillText, id === customerId && styles.pillTextActive]}>#{id}</Text>
            </Pressable>
          ))}
        </View>

        <Text style={styles.sectionTitle}>Settings</Text>
        <Text style={styles.sectionHint}>
          API address of your backend. Use your computer's LAN IP, not "localhost" — your phone
          can't see your computer's localhost. See config.js for how to find it.
        </Text>
        <View style={styles.settingsRow}>
          <TextInput
            style={styles.input}
            value={draftApiBase}
            onChangeText={setDraftApiBase}
            placeholder="http://192.168.1.23:8000"
            autoCapitalize="none"
            autoCorrect={false}
          />
          <Pressable style={styles.saveBtn} onPress={saveApiBase}>
            <Text style={styles.saveBtnText}>Save</Text>
          </Pressable>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#F7F9FC' },
  scroll: { padding: 20, paddingBottom: 40 },
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 20 },
  logoMark: {
    width: 38, height: 38, borderRadius: 11, backgroundColor: '#2F6FED',
    alignItems: 'center', justifyContent: 'center',
  },
  logoMarkText: { color: 'white', fontWeight: '800', fontSize: 17 },
  brand: { fontSize: 17, fontWeight: '700', color: '#1A2233' },
  brandSub: { fontSize: 12, color: '#6B7280', marginTop: 1 },
  statusDot: { width: 10, height: 10, borderRadius: 5 },
  dotOk: { backgroundColor: '#16A34A' },
  dotDown: { backgroundColor: '#DC4C3F' },
  dotChecking: { backgroundColor: '#D1D5DB' },

  errorBanner: {
    backgroundColor: '#FEF1F0', borderColor: '#F6C6C1', borderWidth: 1,
    borderRadius: 12, padding: 14, marginBottom: 16,
  },
  errorTitle: { color: '#B3261E', fontWeight: '700', fontSize: 13, marginBottom: 3 },
  errorText: { color: '#8A3D38', fontSize: 12.5 },

  card: {
    backgroundColor: 'white', borderRadius: 16, padding: 18, marginBottom: 24,
    shadowColor: '#1A2233', shadowOpacity: 0.06, shadowRadius: 10, shadowOffset: { width: 0, height: 4 },
    elevation: 2,
  },
  cardLabel: { fontSize: 11.5, color: '#9AA2B1', textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 6 },
  customerName: { fontSize: 22, fontWeight: '700', color: '#1A2233', marginBottom: 14 },
  statRow: { flexDirection: 'row', gap: 10 },
  statBox: { flex: 1, backgroundColor: '#F7F9FC', borderRadius: 12, padding: 12, alignItems: 'center' },
  statValue: { fontSize: 17, fontWeight: '700', color: '#2F6FED' },
  statLabel: { fontSize: 10.5, color: '#6B7280', marginTop: 3, textAlign: 'center' },

  sectionTitle: { fontSize: 13, fontWeight: '700', color: '#1A2233', marginBottom: 4 },
  sectionHint: { fontSize: 12, color: '#6B7280', marginBottom: 12, lineHeight: 17 },
  pillRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 24 },
  pill: {
    paddingVertical: 8, paddingHorizontal: 14, borderRadius: 20,
    backgroundColor: 'white', borderWidth: 1, borderColor: '#E4E7EC',
  },
  pillActive: { backgroundColor: '#2F6FED', borderColor: '#2F6FED' },
  pillText: { fontSize: 12.5, color: '#4B5565', fontWeight: '600' },
  pillTextActive: { color: 'white' },

  settingsRow: { flexDirection: 'row', gap: 8 },
  input: {
    flex: 1, backgroundColor: 'white', borderWidth: 1, borderColor: '#E4E7EC',
    borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 12.5, color: '#1A2233',
  },
  saveBtn: { backgroundColor: '#1A2233', borderRadius: 10, paddingHorizontal: 16, justifyContent: 'center' },
  saveBtnText: { color: 'white', fontWeight: '700', fontSize: 12.5 },
});
