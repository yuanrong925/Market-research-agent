const manifest = (() => {
function __memo(fn) {
	let value;
	return () => value ??= (value = fn());
}

return {
	appDir: "_app",
	appPath: "_app",
	assets: new Set([]),
	mimeTypes: {},
	_: {
		client: {start:"_app/immutable/entry/start.DlHY-a2b.js",app:"_app/immutable/entry/app.DQ5YDc_L.js",imports:["_app/immutable/entry/start.DlHY-a2b.js","_app/immutable/chunks/D5tTlh0z.js","_app/immutable/chunks/C_UrnoDF.js","_app/immutable/chunks/BKKdqXeL.js","_app/immutable/entry/app.DQ5YDc_L.js","_app/immutable/chunks/BjzOefPn.js","_app/immutable/chunks/C_UrnoDF.js","_app/immutable/chunks/BKKdqXeL.js","_app/immutable/chunks/CmXm4IEf.js","_app/immutable/chunks/CtBYMiYI.js"],stylesheets:[],fonts:[],uses_env_dynamic_public:false},
		nodes: [
			__memo(() => import('./chunks/0-BDV0axiB.js')),
			__memo(() => import('./chunks/1-XNMiDhvf.js')),
			__memo(() => import('./chunks/2-DQcH4kU_.js').then(function (n) { return n._; }))
		],
		remotes: {
			
		},
		routes: [
			{
				id: "/[...catchall]",
				pattern: /^(?:\/([^]*))?\/?$/,
				params: [{"name":"catchall","optional":false,"rest":true,"chained":true}],
				page: { layouts: [0,], errors: [1,], leaf: 2 },
				endpoint: null
			}
		],
		prerendered_routes: new Set([]),
		matchers: async () => {
			
			return {  };
		},
		server_assets: {}
	}
}
})();

const prerendered = new Set([]);

const base = "";

export { base, manifest, prerendered };
//# sourceMappingURL=manifest.js.map
