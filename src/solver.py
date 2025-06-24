class Solver:
    def __init__(self):
        self.counter = 0
        self.mt = []
        self.state = False
        
        self.cache_harden = {}
        self.cache_predict = {}
        self.cache_decode = {}

        self.dp_stats = {
            'operations': {
                'harden': {'cache_hits': 0, 'computes': 0, 'total_cost': 0},
                'predict': {'cache_hits': 0, 'computes': 0, 'total_cost': 0},
                'decode': {'cache_hits': 0, 'computes': 0, 'total_cost': 0},
                'submit': {'cache_hits': 0, 'computes': 0, 'total_cost': 0}
            },
            'total_operations': 0,
            'total_cache_hits': 0,
            'total_cost_saved': 0
        }

        self.operation_costs = {
            'harden': 3,
            'decode': 5,
            'predict': 1,
            'submit': 2
        }
    
    def _dp_cache_lookup(self, operation, cache_key):
        cache_map = {
            'harden': self.cache_harden,
            'predict': self.cache_predict,
            'decode': self.cache_decode
        }
        
        self.dp_stats['total_operations'] += 1
        
        if cache_key in cache_map[operation]:
            self.dp_stats['operations'][operation]['cache_hits'] += 1
            self.dp_stats['total_cache_hits'] += 1

            cost_saved = self.operation_costs[operation]
            self.dp_stats['total_cost_saved'] += cost_saved
            self.dp_stats['operations'][operation]['total_cost'] += 0
            
            return cache_map[operation][cache_key], True
        else:
            self.dp_stats['operations'][operation]['computes'] += 1
            compute_cost = self.operation_costs[operation]
            self.dp_stats['operations'][operation]['total_cost'] += compute_cost
            
            return None, False
    
    def _dp_cache_store(self, operation, cache_key, result):
        cache_map = {
            'harden': self.cache_harden,
            'predict': self.cache_predict,
            'decode': self.cache_decode
        }
        cache_map[operation][cache_key] = result
    
    def submit(self, num):
        if self.state:
            raise ValueError("Already got enough bits")
        
        bits = self._to_bitarray(num)
        assert all([x == 0 or x == 1 for x in bits])
        
        self.dp_stats['operations']['submit']['computes'] += 1
        
        self.counter += 1
        self.mt.append(self._harden_inverse(bits))
        
        if self.counter == 624:
            self._regen()
            self.state = True
    
    def _predict_32(self):
        if not self.state:
            raise ValueError("Didn't receive enough bits to predict")

        cache_key = (self.counter, tuple(self.mt[self.counter % 624]))

        cached_result, is_cache_hit = self._dp_cache_lookup('predict', cache_key)
        
        if is_cache_hit:
            self.counter += 1
            return cached_result
        
        if self.counter >= 624:
            self._regen()
        
        self.counter += 1
        result = self._harden(self.mt[self.counter - 1])
        
        self._dp_cache_store('predict', cache_key, result)
        return result
    
    def predict_getrandbits(self, k):
        if not self.state:
            raise ValueError("Didn't receive enough bits to predict")
        
        if k == 0:
            return 0
            
        words = (k - 1) // 32 + 1
        res = []
        
        for i in range(words):
            r = self._predict_32()
            if k < 32:
                r = [0] * (32 - k) + r[:k]
            res = r + res
            k -= 32
            
        return self._to_int(res)
    
    def predict_randbelow(self, n):
        k = n.bit_length()
        r = self.predict_getrandbits(k)
        while r >= n:
            r = self.predict_getrandbits(k)
        return r
    
    def predict_randrange(self, start, stop=None, step=1, _int=int):
        istart = _int(start)
        if istart != start:
            raise ValueError("non-integer arg 1 for randrange()")
            
        if stop is None:
            if istart > 0:
                return self.predict_randbelow(istart)
            raise ValueError("empty range for randrange()")
        
        istop = _int(stop)
        if istop != stop:
            raise ValueError("non-integer stop for randrange()")
            
        width = istop - istart
        if step == 1 and width > 0:
            return istart + self.predict_randbelow(width)
            
        if step == 1:
            raise ValueError("empty range for randrange() (%d,%d, %d)" % (istart, istop, width))
        
        istep = _int(step)
        if istep != step:
            raise ValueError("non-integer step for randrange()")
            
        if istep > 0:
            n = (width + istep - 1) // istep
        elif istep < 0:
            n = (width + istep + 1) // istep
        else:
            raise ValueError("zero step for randrange()")
        
        if n <= 0:
            raise ValueError("empty range for randrange()")
        
        return istart + istep * self.predict_randbelow(n)
    
    def predict_randint(self, a, b):
        return self.predict_randrange(a, b + 1)
    
    def predict_choice(self, seq):
        try:
            i = self.predict_randbelow(len(seq))
        except ValueError:
            raise IndexError('Cannot choose from an empty sequence')
        return seq[i]
    
    def predict_random(self):
        a = self._to_int(self._predict_32()) >> 5
        b = self._to_int(self._predict_32()) >> 6
        return ((a * 67108864.0) + b) / 9007199254740992.0
    
    def _to_bitarray(self, num):
        k = [int(x) for x in bin(num)[2:]]
        return [0] * (32 - len(k)) + k
    
    def _to_int(self, bits):
        return int("".join(str(i) for i in bits), 2)
    
    def _or_nums(self, a, b):
        if len(a) < 32:
            a = [0] * (32 - len(a)) + a
        if len(b) < 32:
            b = [0] * (32 - len(b)) + b
        return [x[0] | x[1] for x in zip(a, b)]
    
    def _xor_nums(self, a, b):
        if len(a) < 32:
            a = [0] * (32 - len(a)) + a
        if len(b) < 32:
            b = [0] * (32 - len(b)) + b
        return [x[0] ^ x[1] for x in zip(a, b)]
    
    def _and_nums(self, a, b):
        if len(a) < 32:
            a = [0] * (32 - len(a)) + a
        if len(b) < 32:
            b = [0] * (32 - len(b)) + b
        return [x[0] & x[1] for x in zip(a, b)]
    
    def _decode_harden_midop_dp(self, enc, and_arr, shift):
        cache_key = (tuple(enc), tuple(and_arr), shift)

        cached_result, is_cache_hit = self._dp_cache_lookup('decode', cache_key)
        
        if is_cache_hit:
            return cached_result

        dp = [None] * 32
        state = ['NEW'] * 32

        for i in range(32):
            dp[i] = enc[i]
        
        for i in range(32):
            if i >= 32 - shift:
                state[i] = 'OK'
            elif and_arr[i] == 0:
                state[i] = 'OK'
            else:
                state[i] = 'XOR'

        max_iterations = 32
        iteration = 0
        
        while 'XOR' in state and iteration < max_iterations:
            iteration += 1
            changes = False
            
            for i in range(32):
                if state[i] == 'XOR':
                    i_other = i + shift
                    if i_other < 32 and state[i_other] == 'OK':
                        # DP transition: dp[i] = dp[i] XOR dp[i_other]
                        dp[i] = dp[i] ^ dp[i_other]
                        state[i] = 'OK'
                        changes = True
            
            if not changes:
                break
        
        result = dp[:]

        self._dp_cache_store('decode', cache_key, result)
        return result
    
    def _harden(self, bits):
        cache_key = tuple(bits)

        cached_result, is_cache_hit = self._dp_cache_lookup('harden', cache_key)
        
        if is_cache_hit:
            return cached_result

        result = bits[:]
        result = self._xor_nums(result, result[:-11])
        result = self._xor_nums(result, self._and_nums(result[7:] + [0] * 7, self._to_bitarray(0x9d2c5680)))
        result = self._xor_nums(result, self._and_nums(result[15:] + [0] * 15, self._to_bitarray(0xefc60000)))
        result = self._xor_nums(result, result[:-18])

        self._dp_cache_store('harden', cache_key, result)
        return result
    
    def _harden_inverse(self, bits):
        bits = self._xor_nums(bits, bits[:-18])
        bits = self._decode_harden_midop_dp(bits, self._to_bitarray(0xefc60000), 15)
        bits = self._decode_harden_midop_dp(bits, self._to_bitarray(0x9d2c5680), 7)
        bits = self._xor_nums(bits, [0] * 11 + bits[:11] + [0] * 10)
        bits = self._xor_nums(bits, bits[11:21])
        
        return bits
    
    def _regen(self):
        N = 624
        M = 397
        MATRIX_A = 0x9908b0df
        LOWER_MASK = 0x7fffffff
        UPPER_MASK = 0x80000000
        
        mag01 = [self._to_bitarray(0), self._to_bitarray(MATRIX_A)]
        l_bits = self._to_bitarray(LOWER_MASK)
        u_bits = self._to_bitarray(UPPER_MASK)
        
        for kk in range(0, N - M):
            y = self._or_nums(
                self._and_nums(self.mt[kk], u_bits),
                self._and_nums(self.mt[kk + 1], l_bits)
            )
            self.mt[kk] = self._xor_nums(
                self._xor_nums(self.mt[kk + M], y[:-1]),
                mag01[y[-1] & 1]
            )
        
        for kk in range(N - M, N - 1):
            y = self._or_nums(
                self._and_nums(self.mt[kk], u_bits),
                self._and_nums(self.mt[kk + 1], l_bits)
            )
            self.mt[kk] = self._xor_nums(
                self._xor_nums(self.mt[kk + (M - N)], y[:-1]),
                mag01[y[-1] & 1]
            )
        
        y = self._or_nums(
            self._and_nums(self.mt[N - 1], u_bits),
            self._and_nums(self.mt[0], l_bits)
        )
        self.mt[N - 1] = self._xor_nums(
            self._xor_nums(self.mt[M - 1], y[:-1]),
            mag01[y[-1] & 1]
        )
        
        self.counter = 0
        self.cache_predict.clear()
    
    def untwist(self):
        w, n, m = 32, 624, 397
        a = 0x9908B0DF
        
        MT = [self._to_int(x) for x in self.mt]
        
        for i in range(n - 1, -1, -1):
            result = 0
            tmp = MT[i]
            tmp ^= MT[(i + m) % n]
            
            if tmp & (1 << (w - 1)):
                tmp ^= a
                
            result = (tmp << 1) & (1 << (w - 1))
            tmp = MT[(i - 1 + n) % n]
            tmp ^= MT[(i + m - 1) % n]
            
            if tmp & (1 << (w - 1)):
                tmp ^= a
                result |= 1
                
            result |= (tmp << 1) & ((1 << (w - 1)) - 1)
            MT[i] = result
        
        self.mt = [self._to_bitarray(x) for x in MT]
    
    def offset(self, n):
        if n >= 0:
            for _ in range(n):
                self._predict_32()
        else:
            self.cache_predict.clear()
            self.cache_harden.clear()
            
            for _ in range(-n // 624 + 1):
                self.untwist()
            for _ in range(624 - (-n % 624)):
                self._predict_32()
    
    def clear_cache(self):
        self.cache_harden.clear()
        self.cache_predict.clear()
        self.cache_decode.clear()
        
        for op in self.dp_stats['operations']:
            self.dp_stats['operations'][op] = {'cache_hits': 0, 'computes': 0, 'total_cost': 0}
        
        self.dp_stats['total_operations'] = 0
        self.dp_stats['total_cache_hits'] = 0
        self.dp_stats['total_cost_saved'] = 0