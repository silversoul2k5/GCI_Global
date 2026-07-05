import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Animated,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { fetchOffersForCustomer, redeemOffer } from '../api';
import { useAppConfig } from '../config';

const POLL_INTERVAL_MS = 4000;

export default function OffersScreen() {
  const { apiBase, customerId } = useAppConfig();
  const [offers, setOffers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [redeemingId, setRedeemingId] = useState(null);
  const [banner, setBanner] = useState(null);
  const knownIds = useRef(new Set());
  const bannerAnim = useRef(new Animated.Value(0)).current;
  const isFirstLoad = useRef(true);

  const load = useCallback(
    async ({ silent } = {}) => {
      try {
        const data = await fetchOffersForCustomer(apiBase, customerId);
        setError(null);

        if (!isFirstLoad.current) {
          const newOnes = data.filter((o) => !knownIds.current.has(o.id));
          if (newOnes.length > 0) {
            showBanner(
              newOnes.length === 1
                ? `New offer: ${newOnes[0].offer_type}`
                : `${newOnes.length} new offers just arrived`
            );
          }
        }
        knownIds.current = new Set(data.map((o) => o.id));
        isFirstLoad.current = false;
        setOffers(data);
      } catch (e) {
        if (!silent) setError(e.message);
      } finally {
        setLoading(false);
      }
    },
    [apiBase, customerId]
  );

  const showBanner = (text) => {
    setBanner(text);
    Animated.sequence([
      Animated.timing(bannerAnim, { toValue: 1, duration: 220, useNativeDriver: true }),
      Animated.delay(2600),
      Animated.timing(bannerAnim, { toValue: 0, duration: 220, useNativeDriver: true }),
    ]).start(() => setBanner(null));
  };

  // Reset when switching demo customer, then poll continuously.
  useEffect(() => {
    isFirstLoad.current = true;
    knownIds.current = new Set();
    setLoading(true);
    load();
    const id = setInterval(() => load({ silent: true }), POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const onRedeem = async (offer) => {
    setRedeemingId(offer.id);
    try {
      await redeemOffer(apiBase, offer.id);
      setOffers((prev) =>
        prev.map((o) => (o.id === offer.id ? { ...o, status: 'redeemed', redeemed_at: new Date().toISOString() } : o))
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setRedeemingId(null);
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      {banner && (
        <Animated.View
          style={[
            styles.banner,
            {
              opacity: bannerAnim,
              transform: [{ translateY: bannerAnim.interpolate({ inputRange: [0, 1], outputRange: [-16, 0] }) }],
            },
          ]}
        >
          <Text style={styles.bannerText}>🎁 {banner}</Text>
        </Animated.View>
      )}

      <View style={styles.header}>
        <Text style={styles.title}>Offers for you</Text>
        <Text style={styles.subtitle}>Customer #{customerId} · updates automatically</Text>
      </View>

      {error && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {loading ? (
        <ActivityIndicator style={{ marginTop: 40 }} />
      ) : offers.length === 0 ? (
        <View style={styles.empty}>
          <Text style={styles.emptyEmoji}>📭</Text>
          <Text style={styles.emptyTitle}>No offers right now</Text>
          <Text style={styles.emptyText}>
            When the company sends you something, it'll show up here automatically — no need to
            refresh.
          </Text>
        </View>
      ) : (
        <FlatList
          data={offers}
          keyExtractor={(item) => String(item.id)}
          contentContainerStyle={styles.list}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
          renderItem={({ item }) => (
            <View style={styles.offerCard}>
              <View style={styles.offerHeaderRow}>
                <Text style={styles.offerType}>{item.offer_type}</Text>
                {item.status === 'redeemed' ? (
                  <View style={styles.redeemedBadge}>
                    <Text style={styles.redeemedBadgeText}>✓ Redeemed</Text>
                  </View>
                ) : (
                  <View style={styles.newBadge}>
                    <Text style={styles.newBadgeText}>New</Text>
                  </View>
                )}
              </View>
              <Text style={styles.offerMessage}>{item.message}</Text>
              {item.status === 'sent' ? (
                <Pressable
                  style={[styles.redeemBtn, redeemingId === item.id && styles.redeemBtnDisabled]}
                  onPress={() => onRedeem(item)}
                  disabled={redeemingId === item.id}
                >
                  <Text style={styles.redeemBtnText}>
                    {redeemingId === item.id ? 'Redeeming…' : 'Redeem voucher'}
                  </Text>
                </Pressable>
              ) : (
                <Text style={styles.redeemedAt}>
                  Redeemed {item.redeemed_at ? new Date(item.redeemed_at).toLocaleString() : ''}
                </Text>
              )}
            </View>
          )}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#F7F9FC' },
  header: { paddingHorizontal: 20, paddingTop: 16, paddingBottom: 8 },
  title: { fontSize: 22, fontWeight: '800', color: '#1A2233' },
  subtitle: { fontSize: 12.5, color: '#6B7280', marginTop: 2 },

  banner: {
    position: 'absolute', top: 8, left: 20, right: 20, zIndex: 10,
    backgroundColor: '#1A2233', borderRadius: 12, paddingVertical: 10, paddingHorizontal: 14,
  },
  bannerText: { color: 'white', fontSize: 13, fontWeight: '600', textAlign: 'center' },

  errorBanner: {
    marginHorizontal: 20, backgroundColor: '#FEF1F0', borderColor: '#F6C6C1', borderWidth: 1,
    borderRadius: 12, padding: 12, marginTop: 8,
  },
  errorText: { color: '#8A3D38', fontSize: 12 },

  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 40 },
  emptyEmoji: { fontSize: 40, marginBottom: 10 },
  emptyTitle: { fontSize: 16, fontWeight: '700', color: '#1A2233', marginBottom: 6 },
  emptyText: { fontSize: 12.5, color: '#6B7280', textAlign: 'center', lineHeight: 18 },

  list: { padding: 20, gap: 12 },
  offerCard: {
    backgroundColor: 'white', borderRadius: 16, padding: 16,
    shadowColor: '#1A2233', shadowOpacity: 0.06, shadowRadius: 10, shadowOffset: { width: 0, height: 4 },
    elevation: 2,
  },
  offerHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  offerType: { fontSize: 15.5, fontWeight: '700', color: '#1A2233', flexShrink: 1, paddingRight: 8 },
  offerMessage: { fontSize: 13.5, color: '#4B5565', lineHeight: 19, marginBottom: 14 },

  newBadge: { backgroundColor: '#EAF1FF', borderRadius: 20, paddingHorizontal: 10, paddingVertical: 4 },
  newBadgeText: { color: '#2F6FED', fontSize: 11, fontWeight: '700' },
  redeemedBadge: { backgroundColor: '#E9F9EF', borderRadius: 20, paddingHorizontal: 10, paddingVertical: 4 },
  redeemedBadgeText: { color: '#16A34A', fontSize: 11, fontWeight: '700' },

  redeemBtn: { backgroundColor: '#2F6FED', borderRadius: 12, paddingVertical: 12, alignItems: 'center' },
  redeemBtnDisabled: { opacity: 0.6 },
  redeemBtnText: { color: 'white', fontWeight: '700', fontSize: 13.5 },
  redeemedAt: { fontSize: 11.5, color: '#9AA2B1' },
});
