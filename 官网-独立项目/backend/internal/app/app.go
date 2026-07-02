package app

import (
	"bytes"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"database/sql"
	"embed"
	"encoding/base64"
	"encoding/csv"
	"encoding/json"
	"errors"
	"fmt"
	"html"
	"io"
	"io/fs"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	_ "github.com/go-sql-driver/mysql"
)

//go:embed web/*
var webFiles embed.FS

const dataFile = "storage/official-site.json"
const mysqlSchemaVersion = 1
const defaultPublicDomain = "https://www.dtcall.cn"

var adminSessions sync.Map

var htmlTagPattern = regexp.MustCompile(`<[^>]*>`)

type Store struct {
	mu      sync.RWMutex
	path    string
	data    SiteData
	db      *sql.DB
	storage string
}

type SiteData struct {
	Site       SiteConfig       `json:"site"`
	Navigation []NavigationItem `json:"navigation"`
	Pages      []Page           `json:"pages"`
	Products   []Product        `json:"products"`
	Solutions  []ContentItem    `json:"solutions"`
	Cases      []ContentItem    `json:"cases"`
	News       []ContentItem    `json:"news"`
	Resources  []Resource       `json:"resources"`
	FAQs       []FAQ            `json:"faqs"`
	Releases   []Release        `json:"releases"`
	Leads      []Lead           `json:"leads"`
	Users      []AdminUser      `json:"users"`
	Roles      []Role           `json:"roles"`
	Logs       []OperationLog   `json:"logs"`
	UpdatedAt  string           `json:"updatedAt"`
	NextLeadID int              `json:"nextLeadId"`
	NextLogID  int              `json:"nextLogId"`
	NextItemID int              `json:"nextItemId"`
}

type SiteConfig struct {
	SiteName       string `json:"siteName"`
	Slogan         string `json:"slogan"`
	Logo           string `json:"logo"`
	Favicon        string `json:"favicon"`
	Phone          string `json:"phone"`
	Email          string `json:"email"`
	Address        string `json:"address"`
	ICP            string `json:"icp"`
	Domain         string `json:"domain"`
	ThemePrimary   string `json:"themePrimary"`
	SeoTitle       string `json:"seoTitle"`
	SeoKeywords    string `json:"seoKeywords"`
	SeoDescription string `json:"seoDescription"`
	OgImage        string `json:"ogImage"`
}

type NavigationItem struct {
	ID       int    `json:"id"`
	Title    string `json:"title"`
	Path     string `json:"path"`
	Position string `json:"position"`
	Target   string `json:"target"`
	Sort     int    `json:"sort"`
	Enabled  bool   `json:"enabled"`
}

type SEO struct {
	Title       string `json:"title"`
	Keywords    string `json:"keywords"`
	Description string `json:"description"`
	Canonical   string `json:"canonical"`
	OgTitle     string `json:"ogTitle"`
	OgDesc      string `json:"ogDescription"`
	OgImage     string `json:"ogImage"`
	Schema      string `json:"schema"`
}

type Page struct {
	ID       int         `json:"id"`
	Key      string      `json:"key"`
	Title    string      `json:"title"`
	Path     string      `json:"path"`
	Status   string      `json:"status"`
	SEO      SEO         `json:"seo"`
	Blocks   []PageBlock `json:"blocks"`
	UpdateAt string      `json:"updatedAt"`
}

type PageBlock struct {
	ID         int               `json:"id"`
	BlockKey   string            `json:"blockKey"`
	Title      string            `json:"title"`
	Subtitle   string            `json:"subtitle"`
	Content    string            `json:"content"`
	Image      string            `json:"image"`
	ActionText string            `json:"actionText"`
	ActionLink string            `json:"actionLink"`
	Sort       int               `json:"sort"`
	Status     string            `json:"status"`
	Extra      map[string]string `json:"extra"`
}

type Product struct {
	ID          int      `json:"id"`
	Title       string   `json:"title"`
	Slug        string   `json:"slug"`
	Icon        string   `json:"icon"`
	Summary     string   `json:"summary"`
	Description string   `json:"description"`
	Features    []string `json:"features"`
	Metrics     []Metric `json:"metrics"`
	Sort        int      `json:"sort"`
	Status      string   `json:"status"`
	SEO         SEO      `json:"seo"`
	UpdatedAt   string   `json:"updatedAt"`
}

type Metric struct {
	Label string `json:"label"`
	Value string `json:"value"`
}

type ContentItem struct {
	ID          int      `json:"id"`
	Type        string   `json:"type"`
	Title       string   `json:"title"`
	Slug        string   `json:"slug"`
	Category    string   `json:"category"`
	Cover       string   `json:"cover"`
	Summary     string   `json:"summary"`
	Content     string   `json:"content"`
	Tags        []string `json:"tags"`
	Status      string   `json:"status"`
	Recommended bool     `json:"recommended"`
	PublishedAt string   `json:"publishedAt"`
	UpdatedAt   string   `json:"updatedAt"`
	SEO         SEO      `json:"seo"`
}

type Resource struct {
	ID          int      `json:"id"`
	Title       string   `json:"title"`
	Slug        string   `json:"slug"`
	Category    string   `json:"category"`
	Summary     string   `json:"summary"`
	FileURL     string   `json:"fileUrl"`
	NeedLead    bool     `json:"needLead"`
	Tags        []string `json:"tags"`
	Status      string   `json:"status"`
	PublishedAt string   `json:"publishedAt"`
	SEO         SEO      `json:"seo"`
}

type Release struct {
	ID                   int      `json:"id"`
	Version              string   `json:"version"`
	Title                string   `json:"title"`
	Summary              string   `json:"summary"`
	PackageURL           string   `json:"packageUrl"`
	Checksum             string   `json:"checksum"`
	ChecksumType         string   `json:"checksumType"`
	ManifestURL          string   `json:"manifestUrl"`
	Target               string   `json:"target"`
	Channel              string   `json:"channel"`
	Platform             string   `json:"platform"`
	Build                string   `json:"build"`
	PackageSize          int64    `json:"packageSize"`
	MinSupportedVersion  string   `json:"minSupportedVersion"`
	ForceUpdate          bool     `json:"forceUpdate"`
	DockerImageTags      []string `json:"dockerImageTags"`
	ReleaseNotesMarkdown string   `json:"releaseNotesMarkdown"`
	Status               string   `json:"status"`
	PublishedAt          string   `json:"publishedAt"`
	UpdatedAt            string   `json:"updatedAt"`
	Highlights           []string `json:"highlights"`
}

type FAQ struct {
	ID       int    `json:"id"`
	Question string `json:"question"`
	Answer   string `json:"answer"`
	Category string `json:"category"`
	Sort     int    `json:"sort"`
	Status   string `json:"status"`
}

type Lead struct {
	ID         int            `json:"id"`
	Name       string         `json:"name"`
	Company    string         `json:"company"`
	Phone      string         `json:"phone"`
	Email      string         `json:"email"`
	DemandType string         `json:"demandType"`
	Message    string         `json:"message"`
	Status     string         `json:"status"`
	SourcePath string         `json:"sourcePath"`
	IP         string         `json:"ip"`
	CreatedAt  string         `json:"createdAt"`
	UpdatedAt  string         `json:"updatedAt"`
	Followups  []LeadFollowup `json:"followups"`
}

type LeadFollowup struct {
	User       string `json:"user"`
	Content    string `json:"content"`
	NextAction string `json:"nextAction"`
	CreatedAt  string `json:"createdAt"`
}

type AdminUser struct {
	ID          int    `json:"id"`
	Username    string `json:"username"`
	Password    string `json:"password"`
	DisplayName string `json:"displayName"`
	Role        string `json:"role"`
	Status      string `json:"status"`
	CreatedAt   string `json:"createdAt"`
}

type Role struct {
	ID          int      `json:"id"`
	Name        string   `json:"name"`
	Permissions []string `json:"permissions"`
	CreatedAt   string   `json:"createdAt"`
}

type OperationLog struct {
	ID         int    `json:"id"`
	User       string `json:"user"`
	Action     string `json:"action"`
	TargetType string `json:"targetType"`
	TargetID   int    `json:"targetId"`
	IP         string `json:"ip"`
	CreatedAt  string `json:"createdAt"`
}

type BackupInfo struct {
	File      string `json:"file"`
	Size      int64  `json:"size"`
	CreatedAt string `json:"createdAt"`
}

type APIResponse struct {
	Code    int         `json:"code"`
	Message string      `json:"message"`
	Data    interface{} `json:"data"`
}

type AdminSession struct {
	Token       string    `json:"token"`
	Username    string    `json:"username"`
	DisplayName string    `json:"displayName"`
	Role        string    `json:"role"`
	ExpiresAt   time.Time `json:"expiresAt"`
}

func Run() {
	store, err := NewStore(dataFile)
	if err != nil {
		log.Fatalf("官网数据初始化失败: %v", err)
	}

	mux := http.NewServeMux()
	server := &Server{store: store}
	server.routes(mux)

	addr := ":8099"
	if value := os.Getenv("DTCALL_SITE_ADDR"); value != "" {
		addr = value
	}
	log.Printf("DT 官网服务已启动：http://127.0.0.1%s", addr)
	if err := http.ListenAndServe(addr, securityHeaders(mux)); err != nil {
		log.Fatalf("官网服务启动失败: %v", err)
	}
}

type Server struct {
	store *Store
}

func (s *Server) routes(mux *http.ServeMux) {
	mux.HandleFunc("/api/public/site", s.handlePublicSite)
	mux.HandleFunc("/api/public/navigation", s.handlePublicNavigation)
	mux.HandleFunc("/api/public/pages/", s.handlePublicPage)
	mux.HandleFunc("/api/public/products", s.handlePublicProducts)
	mux.HandleFunc("/api/public/solutions", s.handlePublicSolutions)
	mux.HandleFunc("/api/public/solutions/", s.handlePublicSolutionDetail)
	mux.HandleFunc("/api/public/cases", s.handlePublicCases)
	mux.HandleFunc("/api/public/cases/", s.handlePublicCaseDetail)
	mux.HandleFunc("/api/public/news", s.handlePublicNews)
	mux.HandleFunc("/api/public/news/", s.handlePublicNewsDetail)
	mux.HandleFunc("/api/public/resources", s.handlePublicResources)
	mux.HandleFunc("/api/public/releases", s.handlePublicReleases)
	mux.HandleFunc("/api/public/updates/latest", s.handlePublicLatestRelease)
	mux.HandleFunc("/api/public/seo/", s.handlePublicSEO)
	mux.HandleFunc("/api/public/leads", s.handlePublicLeads)
	mux.HandleFunc("/api/admin/auth/login", s.handleAdminLogin)
	mux.HandleFunc("/api/admin/auth/logout", s.withAuth(s.handleAdminLogout))
	mux.HandleFunc("/api/admin/dashboard", s.withAuth(s.handleAdminDashboard))
	mux.HandleFunc("/api/admin/site", s.withAuth(s.handleAdminSite))
	mux.HandleFunc("/api/admin/navigation", s.withAuth(s.handleAdminNavigation))
	mux.HandleFunc("/api/admin/pages", s.withAuth(s.handleAdminPages))
	mux.HandleFunc("/api/admin/products", s.withAuth(s.handleAdminProducts))
	mux.HandleFunc("/api/admin/solutions", s.withAuth(s.handleAdminSolutions))
	mux.HandleFunc("/api/admin/cases", s.withAuth(s.handleAdminCases))
	mux.HandleFunc("/api/admin/news", s.withAuth(s.handleAdminNews))
	mux.HandleFunc("/api/admin/resources", s.withAuth(s.handleAdminResources))
	mux.HandleFunc("/api/admin/releases", s.withAuth(s.handleAdminReleases))
	mux.HandleFunc("/api/admin/leads", s.withAuth(s.handleAdminLeads))
	mux.HandleFunc("/api/admin/leads/export", s.withAuth(s.handleAdminLeadExport))
	mux.HandleFunc("/api/admin/seo/audit", s.withAuth(s.handleAdminSEOAudit))
	mux.HandleFunc("/api/admin/logs", s.withAuth(s.handleAdminLogs))
	mux.HandleFunc("/api/admin/roles", s.withAuth(s.handleAdminRoles))
	mux.HandleFunc("/api/admin/users", s.withAuth(s.handleAdminUsers))
	mux.HandleFunc("/api/admin/backups", s.withAuth(s.handleAdminBackups))
	mux.HandleFunc("/sitemap.xml", s.handleSitemap)
	mux.HandleFunc("/robots.txt", s.handleRobots)
	mux.HandleFunc("/assets/", s.handleStaticAsset)
	mux.HandleFunc("/", s.handleFrontend)
}

func NewStore(path string) (*Store, error) {
	if dsn := strings.TrimSpace(os.Getenv("DTCALL_SITE_MYSQL_DSN")); dsn != "" {
		return NewMySQLStore(dsn)
	}
	store := &Store{path: path, storage: "json"}
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return nil, err
	}
	if _, err := os.Stat(path); errors.Is(err, os.ErrNotExist) {
		store.data = defaultSiteData()
		if err := store.saveLocked(); err != nil {
			return nil, err
		}
		return store, nil
	}
	fileBytes, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	if err := json.Unmarshal(fileBytes, &store.data); err != nil {
		return nil, err
	}
	original, _ := json.Marshal(store.data)
	store.normalizeLocked()
	normalized, _ := json.Marshal(store.data)
	if !bytes.Equal(original, normalized) {
		if err := store.saveLocked(); err != nil {
			return nil, err
		}
	}
	return store, nil
}

func NewMySQLStore(dsn string) (*Store, error) {
	db, err := sql.Open("mysql", normalizeMySQLDSN(dsn))
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(12)
	db.SetMaxIdleConns(6)
	db.SetConnMaxLifetime(30 * time.Minute)
	if err := db.Ping(); err != nil {
		_ = db.Close()
		return nil, fmt.Errorf("连接官网 MySQL 失败: %w", err)
	}
	store := &Store{db: db, data: defaultSiteData(), storage: "mysql"}
	if err := store.ensureMySQLSchema(); err != nil {
		_ = db.Close()
		return nil, err
	}
	if err := store.loadMySQL(); err != nil {
		_ = db.Close()
		return nil, err
	}
	store.normalizeLocked()
	if err := store.saveLocked(); err != nil {
		_ = db.Close()
		return nil, err
	}
	return store, nil
}

func normalizeMySQLDSN(dsn string) string {
	if strings.Contains(dsn, "parseTime=") {
		return dsn
	}
	separator := "?"
	if strings.Contains(dsn, "?") {
		separator = "&"
	}
	return dsn + separator + "charset=utf8mb4&parseTime=true&loc=Local"
}

func (s *Store) ensureMySQLSchema() error {
	statements := []string{
		`CREATE TABLE IF NOT EXISTS official_site_store (
			id TINYINT UNSIGNED NOT NULL PRIMARY KEY,
			schema_version INT NOT NULL,
			data LONGTEXT NOT NULL,
			created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
			CHECK (JSON_VALID(data))
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci`,
		`CREATE TABLE IF NOT EXISTS official_site_backups (
			id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
			name VARCHAR(180) NOT NULL,
			size BIGINT NOT NULL DEFAULT 0,
			data LONGTEXT NOT NULL,
			created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
			CHECK (JSON_VALID(data)),
			INDEX idx_created_at (created_at)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci`,
	}
	for _, statement := range statements {
		if _, err := s.db.Exec(statement); err != nil {
			return fmt.Errorf("初始化官网 MySQL 表失败: %w", err)
		}
	}
	return nil
}

func (s *Store) loadMySQL() error {
	var raw string
	err := s.db.QueryRow(`SELECT data FROM official_site_store WHERE id = 1`).Scan(&raw)
	if errors.Is(err, sql.ErrNoRows) {
		return nil
	}
	if err != nil {
		return err
	}
	if strings.TrimSpace(raw) == "" {
		return nil
	}
	return json.Unmarshal([]byte(raw), &s.data)
}

func (s *Store) createMySQLBackup(name string, content []byte) error {
	_, err := s.db.Exec(`INSERT INTO official_site_backups (name, size, data) VALUES (?, ?, ?)`, name, len(content), string(content))
	return err
}

func (s *Store) listMySQLBackups() ([]BackupInfo, error) {
	rows, err := s.db.Query(`SELECT name, size, DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s') FROM official_site_backups ORDER BY created_at DESC LIMIT 100`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	items := []BackupInfo{}
	for rows.Next() {
		var item BackupInfo
		if err := rows.Scan(&item.File, &item.Size, &item.CreatedAt); err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, rows.Err()
}

func (s *Store) Snapshot() SiteData {
	s.mu.RLock()
	defer s.mu.RUnlock()
	bytes, _ := json.Marshal(s.data)
	var data SiteData
	_ = json.Unmarshal(bytes, &data)
	return data
}

func (s *Store) Update(mutator func(*SiteData) error) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if err := mutator(&s.data); err != nil {
		return err
	}
	s.normalizeLocked()
	return s.saveLocked()
}

func (s *Store) saveLocked() error {
	s.data.UpdatedAt = nowString()
	bytes, err := json.MarshalIndent(s.data, "", "  ")
	if err != nil {
		return err
	}
	if s.storage == "mysql" {
		_, err = s.db.Exec(`INSERT INTO official_site_store (id, schema_version, data) VALUES (1, ?, ?) ON DUPLICATE KEY UPDATE schema_version = VALUES(schema_version), data = VALUES(data)`, mysqlSchemaVersion, string(bytes))
		return err
	}
	return os.WriteFile(s.path, bytes, 0644)
}

func (s *Store) normalizeLocked() {
	if s.data.Navigation == nil {
		s.data.Navigation = []NavigationItem{}
	}
	if s.data.Pages == nil {
		s.data.Pages = []Page{}
	}
	if s.data.Products == nil {
		s.data.Products = []Product{}
	}
	if s.data.Solutions == nil {
		s.data.Solutions = []ContentItem{}
	}
	if s.data.Cases == nil {
		s.data.Cases = []ContentItem{}
	}
	if s.data.News == nil {
		s.data.News = []ContentItem{}
	}
	if s.data.Resources == nil {
		s.data.Resources = []Resource{}
	}
	if s.data.FAQs == nil {
		s.data.FAQs = []FAQ{}
	}
	if s.data.Releases == nil {
		s.data.Releases = []Release{}
	}
	if s.data.Leads == nil {
		s.data.Leads = []Lead{}
	}
	if s.data.Users == nil {
		s.data.Users = []AdminUser{}
	}
	if s.data.Roles == nil {
		s.data.Roles = []Role{}
	}
	if s.data.Logs == nil {
		s.data.Logs = []OperationLog{}
	}
	if s.data.NextLeadID <= 0 {
		s.data.NextLeadID = 1
		for _, lead := range s.data.Leads {
			if lead.ID >= s.data.NextLeadID {
				s.data.NextLeadID = lead.ID + 1
			}
		}
	}
	if s.data.NextLogID <= 0 {
		s.data.NextLogID = 1
		for _, item := range s.data.Logs {
			if item.ID >= s.data.NextLogID {
				s.data.NextLogID = item.ID + 1
			}
		}
	}
	if s.data.NextItemID <= 0 {
		s.data.NextItemID = 1000
	}
	if s.data.Site.Domain == "" {
		s.data.Site.Domain = "http://127.0.0.1:8099"
	}
	if len(s.data.Users) == 0 {
		s.data.Users = defaultUsers()
	}
	for i := range s.data.Users {
		if s.data.Users[i].Password != "" && !strings.HasPrefix(s.data.Users[i].Password, "sha256:") {
			s.data.Users[i].Password = hashPassword(s.data.Users[i].Password)
		}
	}
	if len(s.data.Roles) == 0 {
		s.data.Roles = defaultRoles()
	}
	if len(s.data.Navigation) == 0 {
		s.data.Navigation = defaultNavigation()
	}
	if len(s.data.Pages) == 0 {
		s.data.Pages = defaultPages(nowString())
	}
	if len(s.data.Products) < 8 {
		s.data.Products = defaultProducts(nowString())
	}
	if len(s.data.News) < 4 {
		s.data.News = defaultNews(nowString())
	}
	if len(s.data.Releases) == 0 {
		s.data.Releases = defaultReleases(nowString())
	}
	applyLegacySiteRefresh(&s.data)
}

func applyLegacySiteRefresh(data *SiteData) {
	refreshLegacySiteConfig(&data.Site)
	refreshLegacyNavigation(data.Navigation)
	refreshLegacyPages(data.Pages)
	refreshLegacyFAQs(&data.FAQs)
	refreshLegacyReleases(&data.Releases)
}

func refreshLegacySiteConfig(site *SiteConfig) {
	if looksLocalDomain(site.Domain) || strings.TrimSpace(site.Domain) == "" {
		site.Domain = defaultPublicDomain
	}
	if site.ThemePrimary == "" || strings.EqualFold(site.ThemePrimary, "#8B5CF6") {
		site.ThemePrimary = "#0D4FBE"
	}
	if site.Slogan == "" || site.Slogan == "AI 驱动的一体化企业数字化管理平台" {
		site.Slogan = "轻奢蓝金未来科技的一体化企业管理平台"
	}
	if site.SeoTitle == "" || strings.Contains(site.SeoTitle, "AI 驱动的一体化企业管理平台") {
		site.SeoTitle = "DT 企业智能管理系统 - CRM、合同、财务、项目、OA 一体化企业管理平台"
	}
	if site.SeoKeywords == "" || strings.Contains(site.SeoKeywords, "生产管理系统") {
		site.SeoKeywords = "企业管理系统,CRM系统,合同管理系统,财务管理系统,项目管理系统,OA系统,私有化部署,在线更新,更新中心,企业一体化平台"
	}
	if site.SeoDescription == "" || strings.Contains(site.SeoDescription, "生产、项目、OA") {
		site.SeoDescription = "DT 企业智能管理系统覆盖 CRM、合同、财务、项目、OA、AI 协同、私有化部署与官网更新中心，帮助企业构建统一流程、统一数据和持续升级能力。"
	}
}

func refreshLegacyNavigation(items []NavigationItem) {
	for i := range items {
		if items[i].Path == "/updates" && (items[i].Title == "版本更新" || strings.TrimSpace(items[i].Title) == "") {
			items[i].Title = "更新中心"
		}
	}
}

func refreshLegacyPages(items []Page) {
	for i := range items {
		page := &items[i]
		switch page.Key {
		case "home":
			if page.SEO.Title == "" || strings.Contains(page.SEO.Title, "AI 驱动的一体化企业管理平台") || needsCanonicalRefresh(page.SEO.Canonical) {
				page.SEO = defaultSEO("DT 企业智能管理系统 - CRM、合同、财务、项目、OA 一体化智能管理平台", "面向通用企业管理客户的一体化企业智能管理平台，打通 CRM、合同、财务、项目、OA、AI 协同、私有化部署与官网更新中心。", "/")
			}
			for j := range page.Blocks {
				block := &page.Blocks[j]
				if block.BlockKey == "hero" && (block.Title == "让企业管理进入 AI 协同时代" || strings.TrimSpace(block.Title) == "") {
					block.Title = "企业一体化智能管理平台"
					block.Subtitle = "打通 CRM、合同、财务、项目、OA 与 AI 协同，让企业从分散管理走向统一经营。"
					block.Content = "DT 企业智能管理系统以统一权限、统一流程、统一数据为基础，帮助企业建立可复制、可追踪、可持续优化的经营管理体系，并支持私有化部署与持续在线升级。"
					block.ActionText = "预约产品演示"
					block.ActionLink = "/contact"
				}
				if block.BlockKey == "value" && (block.Title == "把复杂业务装进同一张管理网络" || strings.TrimSpace(block.Title) == "") {
					block.Title = "把复杂经营链路收束到同一张管理网络里"
					block.Subtitle = "从客户线索到合同回款，从项目交付到组织流程，所有关键节点都能被实时看见。"
					block.Content = "通过流程联动、经营看板、AI 智能建议和精细化权限，企业可以减少重复录入、降低沟通成本、提升管理决策速度，并建立面向未来的版本更新与部署能力。"
				}
			}
		case "updates":
			if page.Title == "版本更新" || strings.TrimSpace(page.Title) == "" {
				page.Title = "更新中心"
			}
			if page.SEO.Title == "" || strings.Contains(page.SEO.Title, "版本更新发布") || needsCanonicalRefresh(page.SEO.Canonical) {
				page.SEO = defaultSEO("DT 企业管理系统更新中心 - Docker Compose 在线更新与离线 ZIP", "通过 DT 官网更新中心发布 Linux Docker Compose 升级包、版本目录切换方案、离线 ZIP 包、校验信息和回滚说明，服务客户部署系统持续升级。", "/updates")
			}
			for j := range page.Blocks {
				block := &page.Blocks[j]
				if block.BlockKey == "overview" && (block.Title == "DT 企业管理系统版本发布中心" || strings.TrimSpace(block.Title) == "") {
					block.Title = "DT 企业管理系统更新中心"
					block.Subtitle = "固定域名发布在线升级、离线 ZIP、校验信息与回滚说明"
					block.Content = "更新中心面向已部署客户提供版本号、目标环境、Docker Compose 升级包、版本目录切换、离线 ZIP 导入与升级回滚说明。"
				}
			}
		case "resources":
			if needsCanonicalRefresh(page.SEO.Canonical) {
				page.SEO = defaultSEO("企业管理系统资源中心 - 白皮书 手册 FAQ 部署说明", "获取 DT 企业智能管理系统白皮书、产品手册、部署说明、更新指南和常见问题，帮助企业更快完成数字化管理选型。", "/resources")
			}
		case "contact":
			if needsCanonicalRefresh(page.SEO.Canonical) {
				page.SEO = defaultSEO("联系 DT 企业智能管理系统 - 预约演示 获取方案", "联系 DT 企业智能管理系统商务团队，预约产品演示、获取行业方案、咨询私有化部署、在线更新与企业数字化升级路径。", "/contact")
			}
		default:
			if needsCanonicalRefresh(page.SEO.Canonical) {
				page.SEO.Canonical = buildCanonical(page.Path)
			}
		}
	}
}

func refreshLegacyFAQs(items *[]FAQ) {
	if len(*items) == 0 {
		*items = defaultFAQs()
		return
	}
	for i := range *items {
		item := &(*items)[i]
		switch item.Question {
		case "DT 企业管理系统版本更新如何发布给客户？":
			item.Answer = "通过官网更新中心统一发布版本号、升级说明、Docker Compose 在线更新包、离线 ZIP 包、校验信息与回滚说明，客户部署后可通过固定公网域名检测更新。"
		}
	}
	if len(*items) < 4 {
		*items = defaultFAQs()
	}
}

func refreshLegacyReleases(items *[]Release) {
	if len(*items) == 0 {
		*items = defaultReleases(nowString())
		return
	}
	legacy := len(*items) <= 2 && ((*items)[0].Version == "v3.6.0" || (*items)[0].Version == "v3.5.2" || strings.Contains((*items)[0].Target, "MySQL 8.0"))
	if legacy {
		*items = defaultReleases(nowString())
	}
}

func looksLocalDomain(value string) bool {
	lower := strings.ToLower(strings.TrimSpace(value))
	return lower == "" || strings.Contains(lower, "127.0.0.1") || strings.Contains(lower, "localhost")
}

func needsCanonicalRefresh(value string) bool {
	return looksLocalDomain(value)
}

func buildCanonical(path string) string {
	normalized := strings.TrimSpace(path)
	if normalized == "" {
		normalized = "/"
	}
	if !strings.HasPrefix(normalized, "/") {
		normalized = "/" + normalized
	}
	return strings.TrimRight(defaultPublicDomain, "/") + normalized
}

func writeJSON(w http.ResponseWriter, status int, message string, data interface{}) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(APIResponse{Code: status, Message: message, Data: data})
}

func decodeJSON(r *http.Request, target interface{}) error {
	defer r.Body.Close()
	decoder := json.NewDecoder(io.LimitReader(r.Body, 2<<20))
	decoder.DisallowUnknownFields()
	return decoder.Decode(target)
}

func nowString() string {
	return time.Now().Format("2006-01-02 15:04:05")
}

func published(status string) bool {
	return status == "" || status == "published"
}

func compareSort(a, b NavigationItem) bool {
	if a.Sort == b.Sort {
		return a.ID < b.ID
	}
	return a.Sort < b.Sort
}

func publicPageData(data SiteData, key string) (Page, bool) {
	for _, page := range data.Pages {
		if (page.Key == key || strings.Trim(page.Path, "/") == strings.Trim(key, "/")) && published(page.Status) {
			sort.Slice(page.Blocks, func(i, j int) bool { return page.Blocks[i].Sort < page.Blocks[j].Sort })
			return page, true
		}
	}
	return Page{}, false
}

func filterProducts(items []Product) []Product {
	result := make([]Product, 0, len(items))
	for _, item := range items {
		if published(item.Status) {
			result = append(result, item)
		}
	}
	sort.Slice(result, func(i, j int) bool { return result[i].Sort < result[j].Sort })
	return result
}

func filterContent(items []ContentItem) []ContentItem {
	result := make([]ContentItem, 0, len(items))
	for _, item := range items {
		if published(item.Status) {
			result = append(result, item)
		}
	}
	sort.Slice(result, func(i, j int) bool { return result[i].PublishedAt > result[j].PublishedAt })
	return result
}

func filterResources(items []Resource) []Resource {
	result := make([]Resource, 0, len(items))
	for _, item := range items {
		if published(item.Status) {
			result = append(result, item)
		}
	}
	sort.Slice(result, func(i, j int) bool { return result[i].PublishedAt > result[j].PublishedAt })
	return result
}

func filterFAQs(items []FAQ) []FAQ {
	result := make([]FAQ, 0, len(items))
	for _, item := range items {
		if published(item.Status) {
			result = append(result, item)
		}
	}
	sort.Slice(result, func(i, j int) bool { return result[i].Sort < result[j].Sort })
	return result
}

func normalizeVersion(value string) string {
	return strings.TrimSpace(strings.TrimPrefix(strings.ToLower(value), "v"))
}

func versionParts(value string) []int {
	normalized := normalizeVersion(value)
	parts := strings.Split(normalized, ".")
	result := make([]int, 0, len(parts))
	for _, part := range parts {
		if part == "" {
			result = append(result, 0)
			continue
		}
		piece := part
		for i, ch := range piece {
			if ch < '0' || ch > '9' {
				piece = piece[:i]
				break
			}
		}
		if piece == "" {
			result = append(result, 0)
			continue
		}
		number, err := strconv.Atoi(piece)
		if err != nil {
			result = append(result, 0)
			continue
		}
		result = append(result, number)
	}
	return result
}

func compareVersions(a, b string) int {
	ap := versionParts(a)
	bp := versionParts(b)
	maxLen := len(ap)
	if len(bp) > maxLen {
		maxLen = len(bp)
	}
	for i := 0; i < maxLen; i++ {
		av := 0
		bv := 0
		if i < len(ap) {
			av = ap[i]
		}
		if i < len(bp) {
			bv = bp[i]
		}
		if av > bv {
			return 1
		}
		if av < bv {
			return -1
		}
	}
	return 0
}

func releaseMatches(release Release, channel, platform string) bool {
	if !published(release.Status) {
		return false
	}
	if strings.TrimSpace(channel) != "" && !strings.EqualFold(strings.TrimSpace(release.Channel), strings.TrimSpace(channel)) {
		return false
	}
	if strings.TrimSpace(platform) != "" && !strings.EqualFold(strings.TrimSpace(release.Platform), strings.TrimSpace(platform)) {
		return false
	}
	return true
}

func latestRelease(items []Release, channel, platform string) (Release, bool) {
	result := make([]Release, 0, len(items))
	for _, item := range items {
		if releaseMatches(item, channel, platform) {
			result = append(result, item)
		}
	}
	if len(result) == 0 {
		return Release{}, false
	}
	sort.Slice(result, func(i, j int) bool {
		cmp := compareVersions(result[i].Version, result[j].Version)
		if cmp == 0 {
			return result[i].PublishedAt > result[j].PublishedAt
		}
		return cmp > 0
	})
	return result[0], true
}

func releaseByVersion(items []Release, version, channel, platform string) (Release, bool) {
	target := normalizeVersion(version)
	if target == "" {
		return Release{}, false
	}
	for _, item := range filterReleases(items) {
		if !releaseMatches(item, channel, platform) {
			continue
		}
		if normalizeVersion(item.Version) == target {
			return item, true
		}
	}
	return Release{}, false
}

func filterReleases(items []Release) []Release {
	result := make([]Release, 0, len(items))
	for _, item := range items {
		if published(item.Status) {
			result = append(result, item)
		}
	}
	sort.Slice(result, func(i, j int) bool {
		cmp := compareVersions(result[i].Version, result[j].Version)
		if cmp == 0 {
			return result[i].PublishedAt > result[j].PublishedAt
		}
		return cmp > 0
	})
	return result
}

func findContent(items []ContentItem, slug string) (ContentItem, bool) {
	for _, item := range items {
		if item.Slug == slug && published(item.Status) {
			return item, true
		}
	}
	return ContentItem{}, false
}

func (s *Server) handlePublicSite(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, "请求方法不允许", nil)
		return
	}
	writeJSON(w, http.StatusOK, "获取成功", s.store.Snapshot().Site)
}

func (s *Server) handlePublicNavigation(w http.ResponseWriter, r *http.Request) {
	data := s.store.Snapshot()
	items := make([]NavigationItem, 0, len(data.Navigation))
	for _, item := range data.Navigation {
		if item.Enabled {
			items = append(items, item)
		}
	}
	sort.Slice(items, func(i, j int) bool { return compareSort(items[i], items[j]) })
	writeJSON(w, http.StatusOK, "获取成功", items)
}

func (s *Server) handlePublicPage(w http.ResponseWriter, r *http.Request) {
	key := strings.TrimPrefix(r.URL.Path, "/api/public/pages/")
	page, ok := publicPageData(s.store.Snapshot(), key)
	if !ok {
		writeJSON(w, http.StatusNotFound, "页面不存在", nil)
		return
	}
	writeJSON(w, http.StatusOK, "获取成功", page)
}

func (s *Server) handlePublicProducts(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, "获取成功", filterProducts(s.store.Snapshot().Products))
}

func (s *Server) handlePublicSolutions(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, "获取成功", filterContent(s.store.Snapshot().Solutions))
}

func (s *Server) handlePublicSolutionDetail(w http.ResponseWriter, r *http.Request) {
	slug := strings.TrimPrefix(r.URL.Path, "/api/public/solutions/")
	item, ok := findContent(s.store.Snapshot().Solutions, slug)
	if !ok {
		writeJSON(w, http.StatusNotFound, "内容不存在", nil)
		return
	}
	writeJSON(w, http.StatusOK, "获取成功", item)
}

func (s *Server) handlePublicCases(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, "获取成功", filterContent(s.store.Snapshot().Cases))
}

func (s *Server) handlePublicCaseDetail(w http.ResponseWriter, r *http.Request) {
	slug := strings.TrimPrefix(r.URL.Path, "/api/public/cases/")
	item, ok := findContent(s.store.Snapshot().Cases, slug)
	if !ok {
		writeJSON(w, http.StatusNotFound, "内容不存在", nil)
		return
	}
	writeJSON(w, http.StatusOK, "获取成功", item)
}

func (s *Server) handlePublicNews(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, "获取成功", filterContent(s.store.Snapshot().News))
}

func (s *Server) handlePublicNewsDetail(w http.ResponseWriter, r *http.Request) {
	slug := strings.TrimPrefix(r.URL.Path, "/api/public/news/")
	item, ok := findContent(s.store.Snapshot().News, slug)
	if !ok {
		writeJSON(w, http.StatusNotFound, "内容不存在", nil)
		return
	}
	writeJSON(w, http.StatusOK, "获取成功", item)
}

func (s *Server) handlePublicResources(w http.ResponseWriter, r *http.Request) {
	data := s.store.Snapshot()
	writeJSON(w, http.StatusOK, "获取成功", map[string]interface{}{
		"resources": filterResources(data.Resources),
		"faqs":      filterFAQs(data.FAQs),
	})
}

func (s *Server) handlePublicReleases(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, "获取成功", filterReleases(s.store.Snapshot().Releases))
}

func (s *Server) handlePublicLatestRelease(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, "请求方法不允许", nil)
		return
	}
	channel := strings.TrimSpace(r.URL.Query().Get("channel"))
	if channel == "" {
		channel = "stable"
	}
	platform := strings.TrimSpace(r.URL.Query().Get("platform"))
	if platform == "" {
		platform = "linux-docker-x64"
	}
	currentVersion := strings.TrimSpace(r.URL.Query().Get("version"))
	releaseVersion := strings.TrimSpace(r.URL.Query().Get("releaseVersion"))

	var (
		release Release
		ok      bool
	)
	if releaseVersion != "" {
		release, ok = releaseByVersion(s.store.Snapshot().Releases, releaseVersion, channel, platform)
	} else {
		release, ok = latestRelease(s.store.Snapshot().Releases, channel, platform)
	}
	if !ok {
		writeJSON(w, http.StatusNotFound, "未找到可用更新版本", map[string]interface{}{
			"channel":         channel,
			"platform":        platform,
			"releaseVersion":  releaseVersion,
			"updateAvailable": false,
		})
		return
	}

	updateAvailable := false
	if currentVersion != "" {
		updateAvailable = compareVersions(release.Version, currentVersion) > 0
	}

	writeJSON(w, http.StatusOK, "获取成功", map[string]interface{}{
		"channel":         release.Channel,
		"platform":        release.Platform,
		"currentVersion":  currentVersion,
		"releaseVersion":  release.Version,
		"latestVersion":   release.Version,
		"updateAvailable": updateAvailable,
		"release":         release,
		"releaseNotes":    release.ReleaseNotesMarkdown,
		"highlights":      release.Highlights,
	})
}

func (s *Server) handlePublicSEO(w http.ResponseWriter, r *http.Request) {
	path := strings.TrimPrefix(r.URL.Path, "/api/public/seo")
	seo, _ := s.resolveSEO(path)
	writeJSON(w, http.StatusOK, "获取成功", seo)
}

func (s *Server) handlePublicLeads(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, "请求方法不允许", nil)
		return
	}
	var lead Lead
	if err := decodeJSON(r, &lead); err != nil {
		writeJSON(w, http.StatusBadRequest, "线索数据格式不正确", nil)
		return
	}
	lead.Name = strings.TrimSpace(lead.Name)
	lead.Phone = strings.TrimSpace(lead.Phone)
	if lead.Name == "" || lead.Phone == "" {
		writeJSON(w, http.StatusBadRequest, "姓名和联系电话不能为空", nil)
		return
	}
	err := s.store.Update(func(data *SiteData) error {
		lead.ID = data.NextLeadID
		data.NextLeadID++
		lead.Status = "new"
		lead.IP = clientIP(r)
		lead.CreatedAt = nowString()
		lead.UpdatedAt = lead.CreatedAt
		data.Leads = append([]Lead{lead}, data.Leads...)
		appendLog(data, "官网访客", "提交咨询线索", "lead", lead.ID, clientIP(r))
		return nil
	})
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, "保存线索失败", nil)
		return
	}
	writeJSON(w, http.StatusOK, "提交成功，我们会尽快联系您", lead)
}

func (s *Server) handleAdminLogin(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, "请求方法不允许", nil)
		return
	}
	var payload struct {
		Username string `json:"username"`
		Password string `json:"password"`
	}
	if err := decodeJSON(r, &payload); err != nil {
		writeJSON(w, http.StatusBadRequest, "登录数据格式不正确", nil)
		return
	}
	var matched AdminUser
	for _, user := range s.store.Snapshot().Users {
		if user.Username == payload.Username && verifyPassword(user.Password, payload.Password) && user.Status == "active" {
			matched = user
			break
		}
	}
	if matched.Username == "" {
		writeJSON(w, http.StatusUnauthorized, "账号或密码不正确", nil)
		return
	}
	token := secureToken()
	session := AdminSession{Token: token, Username: matched.Username, DisplayName: matched.DisplayName, Role: matched.Role, ExpiresAt: time.Now().Add(12 * time.Hour)}
	adminSessions.Store(token, session)
	_ = s.store.Update(func(data *SiteData) error {
		appendLog(data, matched.DisplayName, "登录管理后台", "auth", matched.ID, clientIP(r))
		return nil
	})
	writeJSON(w, http.StatusOK, "登录成功", session)
}

func (s *Server) handleAdminLogout(w http.ResponseWriter, r *http.Request) {
	token := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
	adminSessions.Delete(token)
	writeJSON(w, http.StatusOK, "退出成功", true)
}

func (s *Server) handleAdminDashboard(w http.ResponseWriter, r *http.Request) {
	data := s.store.Snapshot()
	newLeads := 0
	for _, lead := range data.Leads {
		if lead.Status == "new" {
			newLeads++
		}
	}
	writeJSON(w, http.StatusOK, "获取成功", map[string]interface{}{
		"pageCount":     len(data.Pages),
		"productCount":  len(data.Products),
		"solutionCount": len(data.Solutions),
		"caseCount":     len(data.Cases),
		"newsCount":     len(data.News),
		"releaseCount":  len(data.Releases),
		"contentCount":  len(data.Solutions) + len(data.Cases) + len(data.News) + len(data.Resources) + len(data.Releases),
		"leadCount":     len(data.Leads),
		"newLeadCount":  newLeads,
		"seoIssues":     buildSEOAudit(data),
		"recentLeads":   firstLeads(data.Leads, 6),
		"recentLogs":    firstLogs(data.Logs, 8),
		"updatedAt":     data.UpdatedAt,
	})
}

func (s *Server) handleAdminSite(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet {
		writeJSON(w, http.StatusOK, "获取成功", s.store.Snapshot().Site)
		return
	}
	if r.Method != http.MethodPut && r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, "请求方法不允许", nil)
		return
	}
	var site SiteConfig
	if err := decodeJSON(r, &site); err != nil {
		writeJSON(w, http.StatusBadRequest, "站点配置格式不正确", nil)
		return
	}
	session := currentSession(r)
	_ = s.store.Update(func(data *SiteData) error {
		data.Site = site
		appendLog(data, session.DisplayName, "更新站点配置", "site", 0, clientIP(r))
		return nil
	})
	writeJSON(w, http.StatusOK, "保存成功", site)
}

func (s *Server) handleAdminNavigation(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet {
		writeJSON(w, http.StatusOK, "获取成功", s.store.Snapshot().Navigation)
		return
	}
	var items []NavigationItem
	if err := decodeJSON(r, &items); err != nil {
		writeJSON(w, http.StatusBadRequest, "导航数据格式不正确", nil)
		return
	}
	session := currentSession(r)
	_ = s.store.Update(func(data *SiteData) error {
		data.Navigation = items
		appendLog(data, session.DisplayName, "更新官网导航", "navigation", 0, clientIP(r))
		return nil
	})
	writeJSON(w, http.StatusOK, "保存成功", items)
}

func (s *Server) handleAdminPages(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet {
		writeJSON(w, http.StatusOK, "获取成功", s.store.Snapshot().Pages)
		return
	}
	var items []Page
	if err := decodeJSON(r, &items); err != nil {
		writeJSON(w, http.StatusBadRequest, "页面数据格式不正确", nil)
		return
	}
	session := currentSession(r)
	_ = s.store.Update(func(data *SiteData) error {
		data.Pages = items
		appendLog(data, session.DisplayName, "更新页面区块", "page", 0, clientIP(r))
		return nil
	})
	writeJSON(w, http.StatusOK, "保存成功", items)
}

func (s *Server) handleAdminProducts(w http.ResponseWriter, r *http.Request) {
	s.handleProductCollection(w, r)
}

func (s *Server) handleAdminSolutions(w http.ResponseWriter, r *http.Request) {
	s.handleContentCollection(w, r, "solution")
}

func (s *Server) handleAdminCases(w http.ResponseWriter, r *http.Request) {
	s.handleContentCollection(w, r, "case")
}

func (s *Server) handleAdminNews(w http.ResponseWriter, r *http.Request) {
	s.handleContentCollection(w, r, "news")
}

func (s *Server) handleAdminResources(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet {
		data := s.store.Snapshot()
		writeJSON(w, http.StatusOK, "获取成功", map[string]interface{}{"resources": data.Resources, "faqs": data.FAQs})
		return
	}
	var payload struct {
		Resources []Resource `json:"resources"`
		FAQs      []FAQ      `json:"faqs"`
	}
	if err := decodeJSON(r, &payload); err != nil {
		writeJSON(w, http.StatusBadRequest, "资源数据格式不正确", nil)
		return
	}
	session := currentSession(r)
	_ = s.store.Update(func(data *SiteData) error {
		data.Resources = payload.Resources
		data.FAQs = payload.FAQs
		appendLog(data, session.DisplayName, "更新资源与 FAQ", "resource", 0, clientIP(r))
		return nil
	})
	writeJSON(w, http.StatusOK, "保存成功", payload)
}

func (s *Server) handleAdminReleases(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet {
		writeJSON(w, http.StatusOK, "获取成功", s.store.Snapshot().Releases)
		return
	}
	if r.Method != http.MethodPut && r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, "请求方法不允许", nil)
		return
	}
	var items []Release
	if err := decodeJSON(r, &items); err != nil {
		writeJSON(w, http.StatusBadRequest, "版本发布数据格式不正确", nil)
		return
	}
	session := currentSession(r)
	_ = s.store.Update(func(data *SiteData) error {
		for i := range items {
			if items[i].ID <= 0 {
				items[i].ID = data.NextItemID
				data.NextItemID++
			}
			if strings.TrimSpace(items[i].PublishedAt) == "" {
				items[i].PublishedAt = nowString()
			}
			items[i].UpdatedAt = nowString()
		}
		data.Releases = items
		appendLog(data, session.DisplayName, "更新 DT 系统版本发布", "release", 0, clientIP(r))
		return nil
	})
	writeJSON(w, http.StatusOK, "保存成功", items)
}

func (s *Server) handleProductCollection(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet {
		writeJSON(w, http.StatusOK, "获取成功", s.store.Snapshot().Products)
		return
	}
	var items []Product
	if err := decodeJSON(r, &items); err != nil {
		writeJSON(w, http.StatusBadRequest, "产品数据格式不正确", nil)
		return
	}
	session := currentSession(r)
	_ = s.store.Update(func(data *SiteData) error {
		data.Products = items
		appendLog(data, session.DisplayName, "更新产品能力", "product", 0, clientIP(r))
		return nil
	})
	writeJSON(w, http.StatusOK, "保存成功", items)
}

func (s *Server) handleContentCollection(w http.ResponseWriter, r *http.Request, kind string) {
	if r.Method == http.MethodGet {
		data := s.store.Snapshot()
		writeJSON(w, http.StatusOK, "获取成功", contentByKind(data, kind))
		return
	}
	var items []ContentItem
	if err := decodeJSON(r, &items); err != nil {
		writeJSON(w, http.StatusBadRequest, "内容数据格式不正确", nil)
		return
	}
	session := currentSession(r)
	_ = s.store.Update(func(data *SiteData) error {
		switch kind {
		case "solution":
			data.Solutions = items
		case "case":
			data.Cases = items
		case "news":
			data.News = items
		}
		appendLog(data, session.DisplayName, "更新内容", kind, 0, clientIP(r))
		return nil
	})
	writeJSON(w, http.StatusOK, "保存成功", items)
}

func (s *Server) handleAdminLeads(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet {
		leads := s.store.Snapshot().Leads
		if leads == nil {
			leads = []Lead{}
		}
		writeJSON(w, http.StatusOK, "获取成功", leads)
		return
	}
	if r.Method != http.MethodPut && r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, "请求方法不允许", nil)
		return
	}
	var leads []Lead
	decoder := json.NewDecoder(io.LimitReader(r.Body, 2<<20))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&leads); err != nil {
		writeJSON(w, http.StatusBadRequest, "线索数据格式不正确", nil)
		return
	}
	session := currentSession(r)
	err := s.store.Update(func(data *SiteData) error {
		for i := range leads {
			leads[i].Name = strings.TrimSpace(leads[i].Name)
			leads[i].Phone = strings.TrimSpace(leads[i].Phone)
			if leads[i].ID <= 0 {
				leads[i].ID = data.NextLeadID
				data.NextLeadID++
			}
			if strings.TrimSpace(leads[i].CreatedAt) == "" {
				leads[i].CreatedAt = nowString()
			}
			leads[i].UpdatedAt = nowString()
		}
		data.Leads = leads
		appendLog(data, session.DisplayName, "更新线索管理", "lead", 0, clientIP(r))
		return nil
	})
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, "保存线索失败", nil)
		return
	}
	writeJSON(w, http.StatusOK, "保存成功", leads)
}

func (s *Server) handleAdminLeadExport(w http.ResponseWriter, r *http.Request) {
	data := s.store.Snapshot()
	w.Header().Set("Content-Type", "text/csv; charset=utf-8")
	w.Header().Set("Content-Disposition", "attachment; filename=dtcall-leads.csv")
	_, _ = w.Write([]byte("\xEF\xBB\xBF"))
	writer := csv.NewWriter(w)
	_ = writer.Write([]string{"ID", "姓名", "企业", "电话", "邮箱", "需求类型", "状态", "来源", "留言", "创建时间"})
	for _, lead := range data.Leads {
		_ = writer.Write([]string{strconv.Itoa(lead.ID), lead.Name, lead.Company, lead.Phone, lead.Email, lead.DemandType, lead.Status, lead.SourcePath, lead.Message, lead.CreatedAt})
	}
	writer.Flush()
}

func (s *Server) handleAdminSEOAudit(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, "获取成功", buildSEOAudit(s.store.Snapshot()))
}

func (s *Server) handleAdminLogs(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, "获取成功", s.store.Snapshot().Logs)
}

func (s *Server) handleAdminRoles(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet {
		writeJSON(w, http.StatusOK, "获取成功", s.store.Snapshot().Roles)
		return
	}
	var items []Role
	if err := decodeJSON(r, &items); err != nil {
		writeJSON(w, http.StatusBadRequest, "角色数据格式不正确", nil)
		return
	}
	session := currentSession(r)
	_ = s.store.Update(func(data *SiteData) error {
		data.Roles = items
		appendLog(data, session.DisplayName, "更新后台角色", "role", 0, clientIP(r))
		return nil
	})
	writeJSON(w, http.StatusOK, "保存成功", items)
}

func (s *Server) handleAdminUsers(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet {
		users := s.store.Snapshot().Users
		for i := range users {
			users[i].Password = ""
		}
		writeJSON(w, http.StatusOK, "获取成功", users)
		return
	}
	var items []AdminUser
	if err := decodeJSON(r, &items); err != nil {
		writeJSON(w, http.StatusBadRequest, "用户数据格式不正确", nil)
		return
	}
	existing := s.store.Snapshot().Users
	passwords := map[string]string{}
	for _, user := range existing {
		passwords[user.Username] = user.Password
	}
	for i := range items {
		if items[i].Password == "" {
			items[i].Password = passwords[items[i].Username]
		} else if !strings.HasPrefix(items[i].Password, "sha256:") {
			items[i].Password = hashPassword(items[i].Password)
		}
	}
	session := currentSession(r)
	_ = s.store.Update(func(data *SiteData) error {
		data.Users = items
		appendLog(data, session.DisplayName, "更新后台用户", "user", 0, clientIP(r))
		return nil
	})
	writeJSON(w, http.StatusOK, "保存成功", true)
}

func (s *Server) handleAdminBackups(w http.ResponseWriter, r *http.Request) {
	backupDir := filepath.Join("storage", "backups")
	if r.Method == http.MethodGet {
		backups, err := s.listBackups(backupDir)
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, "读取备份列表失败", nil)
			return
		}
		writeJSON(w, http.StatusOK, "获取成功", backups)
		return
	}
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, "请求方法不允许", nil)
		return
	}
	if err := os.MkdirAll(backupDir, 0755); err != nil {
		writeJSON(w, http.StatusInternalServerError, "创建备份目录失败", nil)
		return
	}
	name := fmt.Sprintf("official-site-%s.json", time.Now().Format("20060102150405"))
	content, err := json.MarshalIndent(s.store.Snapshot(), "", "  ")
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, "读取数据失败", nil)
		return
	}
	if s.store.storage == "mysql" {
		if err := s.store.createMySQLBackup(name, content); err != nil {
			writeJSON(w, http.StatusInternalServerError, "写入 MySQL 备份失败", nil)
			return
		}
		session := currentSession(r)
		_ = s.store.Update(func(data *SiteData) error {
			appendLog(data, session.DisplayName, "创建 MySQL 数据备份", "backup", 0, clientIP(r))
			return nil
		})
		writeJSON(w, http.StatusOK, "备份成功", BackupInfo{File: name, Size: int64(len(content)), CreatedAt: nowString()})
		return
	}
	backupPath := filepath.Join(backupDir, name)
	if err := os.WriteFile(backupPath, content, 0644); err != nil {
		writeJSON(w, http.StatusInternalServerError, "写入备份失败", nil)
		return
	}
	info, _ := os.Stat(backupPath)
	session := currentSession(r)
	_ = s.store.Update(func(data *SiteData) error {
		appendLog(data, session.DisplayName, "创建数据备份", "backup", 0, clientIP(r))
		return nil
	})
	writeJSON(w, http.StatusOK, "备份成功", BackupInfo{File: filepath.ToSlash(backupPath), Size: fileSize(info), CreatedAt: nowString()})
}

func (s *Server) listBackups(dir string) ([]BackupInfo, error) {
	if s.store.storage == "mysql" {
		return s.store.listMySQLBackups()
	}
	entries, err := os.ReadDir(dir)
	if errors.Is(err, os.ErrNotExist) {
		return []BackupInfo{}, nil
	}
	if err != nil {
		return nil, err
	}
	items := make([]BackupInfo, 0, len(entries))
	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".json") {
			continue
		}
		info, err := entry.Info()
		if err != nil {
			continue
		}
		items = append(items, BackupInfo{File: filepath.ToSlash(filepath.Join(dir, entry.Name())), Size: info.Size(), CreatedAt: info.ModTime().Format(time.RFC3339)})
	}
	sort.Slice(items, func(i, j int) bool { return items[i].CreatedAt > items[j].CreatedAt })
	return items, nil
}

func fileSize(info os.FileInfo) int64 {
	if info == nil {
		return 0
	}
	return info.Size()
}

func contentByKind(data SiteData, kind string) []ContentItem {
	switch kind {
	case "solution":
		return data.Solutions
	case "case":
		return data.Cases
	case "news":
		return data.News
	default:
		return nil
	}
}

func (s *Server) withAuth(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		token := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
		value, ok := adminSessions.Load(token)
		if !ok {
			writeJSON(w, http.StatusUnauthorized, "请先登录管理后台", nil)
			return
		}
		session := value.(AdminSession)
		if time.Now().After(session.ExpiresAt) {
			adminSessions.Delete(token)
			writeJSON(w, http.StatusUnauthorized, "登录状态已过期", nil)
			return
		}
		next(w, r)
	}
}

func currentSession(r *http.Request) AdminSession {
	token := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
	value, ok := adminSessions.Load(token)
	if !ok {
		return AdminSession{DisplayName: "系统"}
	}
	return value.(AdminSession)
}

func secureToken() string {
	bytes := make([]byte, 32)
	if _, err := rand.Read(bytes); err != nil {
		fallback := sha256.Sum256([]byte(fmt.Sprintf("%d", time.Now().UnixNano())))
		return base64.RawURLEncoding.EncodeToString(fallback[:])
	}
	return base64.RawURLEncoding.EncodeToString(bytes)
}

func hashPassword(password string) string {
	sum := sha256.Sum256([]byte(password))
	return "sha256:" + base64.RawStdEncoding.EncodeToString(sum[:])
}

func verifyPassword(stored string, password string) bool {
	if stored == "" || password == "" {
		return false
	}
	if !strings.HasPrefix(stored, "sha256:") {
		return subtle.ConstantTimeCompare([]byte(stored), []byte(password)) == 1
	}
	return subtle.ConstantTimeCompare([]byte(stored), []byte(hashPassword(password))) == 1
}

func clientIP(r *http.Request) string {
	if value := r.Header.Get("X-Forwarded-For"); value != "" {
		return strings.TrimSpace(strings.Split(value, ",")[0])
	}
	host := r.RemoteAddr
	if index := strings.LastIndex(host, ":"); index > -1 {
		return host[:index]
	}
	return host
}

func appendLog(data *SiteData, user, action, targetType string, targetID int, ip string) {
	logItem := OperationLog{ID: data.NextLogID, User: user, Action: action, TargetType: targetType, TargetID: targetID, IP: ip, CreatedAt: nowString()}
	data.NextLogID++
	data.Logs = append([]OperationLog{logItem}, data.Logs...)
	if len(data.Logs) > 200 {
		data.Logs = data.Logs[:200]
	}
}

func firstLeads(items []Lead, count int) []Lead {
	if len(items) <= count {
		return items
	}
	return items[:count]
}

func firstLogs(items []OperationLog, count int) []OperationLog {
	if len(items) <= count {
		return items
	}
	return items[:count]
}

func buildSEOAudit(data SiteData) []map[string]string {
	issues := []map[string]string{}
	check := func(path, title string, seo SEO) {
		description := strings.TrimSpace(seo.Description)
		if strings.TrimSpace(seo.Title) == "" {
			issues = append(issues, map[string]string{"path": path, "title": title, "level": "high", "message": "缺少 SEO 标题"})
		}
		if description == "" {
			issues = append(issues, map[string]string{"path": path, "title": title, "level": "high", "message": "缺少 SEO 描述"})
		} else if len([]rune(description)) < 40 {
			issues = append(issues, map[string]string{"path": path, "title": title, "level": "medium", "message": "SEO 描述建议进一步补充行业场景与核心价值"})
		}
		if strings.TrimSpace(seo.Keywords) == "" {
			issues = append(issues, map[string]string{"path": path, "title": title, "level": "medium", "message": "缺少关键词策略"})
		}
		if strings.TrimSpace(seo.Canonical) == "" {
			issues = append(issues, map[string]string{"path": path, "title": title, "level": "low", "message": "缺少 canonical URL"})
		}
	}
	for _, page := range data.Pages {
		check(page.Path, page.Title, page.SEO)
	}
	for _, item := range data.Solutions {
		check("/solutions/"+item.Slug, item.Title, item.SEO)
	}
	for _, item := range data.Cases {
		check("/cases/"+item.Slug, item.Title, item.SEO)
	}
	for _, item := range data.News {
		check("/news/"+item.Slug, item.Title, item.SEO)
	}
	return issues
}

func (s *Server) resolveSEO(path string) (SEO, string) {
	data := s.store.Snapshot()
	cleanPath := "/" + strings.Trim(strings.TrimSpace(path), "/")
	if cleanPath == "/" {
		cleanPath = "/"
	}
	for _, page := range data.Pages {
		if page.Path == cleanPath {
			return enrichSEO(data.Site, page.SEO, page.Title, cleanPath), collectPageText(page)
		}
	}
	lookup := func(prefix string, items []ContentItem) (SEO, string, bool) {
		if strings.HasPrefix(cleanPath, prefix) {
			slug := strings.TrimPrefix(cleanPath, prefix)
			for _, item := range items {
				if item.Slug == slug {
					return enrichSEO(data.Site, item.SEO, item.Title, cleanPath), item.Summary + " " + plainText(item.Content), true
				}
			}
		}
		return SEO{}, "", false
	}
	if seo, text, ok := lookup("/solutions/", data.Solutions); ok {
		return seo, text
	}
	if seo, text, ok := lookup("/cases/", data.Cases); ok {
		return seo, text
	}
	if seo, text, ok := lookup("/news/", data.News); ok {
		return seo, text
	}
	return enrichSEO(data.Site, SEO{}, data.Site.SiteName, cleanPath), data.Site.SeoDescription
}

func enrichSEO(site SiteConfig, seo SEO, fallbackTitle, path string) SEO {
	if seo.Title == "" {
		seo.Title = fallbackTitle + " - " + site.SiteName
	}
	if seo.Keywords == "" {
		seo.Keywords = site.SeoKeywords
	}
	if seo.Description == "" {
		seo.Description = site.SeoDescription
	}
	if seo.Canonical == "" {
		seo.Canonical = strings.TrimRight(site.Domain, "/") + path
	}
	if seo.OgTitle == "" {
		seo.OgTitle = seo.Title
	}
	if seo.OgDesc == "" {
		seo.OgDesc = seo.Description
	}
	if seo.OgImage == "" {
		seo.OgImage = site.OgImage
	}
	if seo.Schema == "" {
		seo.Schema = fmt.Sprintf(`{"@context":"https://schema.org","@type":"WebPage","name":%q,"description":%q,"url":%q}`, seo.Title, seo.Description, seo.Canonical)
	}
	return seo
}

func collectPageText(page Page) string {
	parts := []string{page.Title}
	for _, block := range page.Blocks {
		parts = append(parts, block.Title, block.Subtitle, plainText(block.Content))
	}
	return strings.Join(parts, " ")
}

func plainText(value string) string {
	value = strings.ReplaceAll(value, "<br>", " ")
	value = strings.ReplaceAll(value, "<br/>", " ")
	value = strings.ReplaceAll(value, "<br />", " ")
	value = htmlTagPattern.ReplaceAllString(value, " ")
	return strings.Join(strings.Fields(value), " ")
}

func (s *Server) handleSitemap(w http.ResponseWriter, r *http.Request) {
	data := s.store.Snapshot()
	urls := []string{"/"}
	for _, page := range data.Pages {
		if page.Path != "/" && published(page.Status) {
			urls = append(urls, page.Path)
		}
	}
	for _, item := range filterContent(data.Solutions) {
		urls = append(urls, "/solutions/"+item.Slug)
	}
	for _, item := range filterContent(data.Cases) {
		urls = append(urls, "/cases/"+item.Slug)
	}
	for _, item := range filterContent(data.News) {
		urls = append(urls, "/news/"+item.Slug)
	}
	w.Header().Set("Content-Type", "application/xml; charset=utf-8")
	_, _ = w.Write([]byte(`<?xml version="1.0" encoding="UTF-8"?>` + "\n" + `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">` + "\n"))
	for _, url := range urls {
		loc := strings.TrimRight(data.Site.Domain, "/") + url
		_, _ = fmt.Fprintf(w, "  <url><loc>%s</loc><lastmod>%s</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>\n", html.EscapeString(loc), time.Now().Format("2006-01-02"))
	}
	_, _ = w.Write([]byte(`</urlset>`))
}

func (s *Server) handleRobots(w http.ResponseWriter, r *http.Request) {
	domain := strings.TrimRight(s.store.Snapshot().Site.Domain, "/")
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	_, _ = fmt.Fprintf(w, "User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /api/admin\nSitemap: %s/sitemap.xml\n", domain)
}

func (s *Server) handleStaticAsset(w http.ResponseWriter, r *http.Request) {
	fileServer, err := fs.Sub(webFiles, "web")
	if err != nil {
		http.NotFound(w, r)
		return
	}
	setCacheHeader(w, r.URL.Path)
	http.FileServer(http.FS(fileServer)).ServeHTTP(w, r)
}

func (s *Server) handleFrontend(w http.ResponseWriter, r *http.Request) {
	if strings.HasPrefix(r.URL.Path, "/api/") {
		writeJSON(w, http.StatusNotFound, "接口不存在", nil)
		return
	}
	fileServer, err := fs.Sub(webFiles, "web")
	if err != nil {
		http.NotFound(w, r)
		return
	}
	if r.URL.Path != "/" {
		name := strings.TrimPrefix(r.URL.Path, "/")
		if file, err := fileServer.Open(name); err == nil {
			_ = file.Close()
			setCacheHeader(w, r.URL.Path)
			http.FileServer(http.FS(fileServer)).ServeHTTP(w, r)
			return
		}
	}
	content, err := fs.ReadFile(fileServer, "index.html")
	if err != nil {
		http.NotFound(w, r)
		return
	}
	seo, text := s.resolveSEO(r.URL.Path)
	htmlContent := injectSEO(string(content), seo, text)
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	_, _ = w.Write([]byte(htmlContent))
}

func setCacheHeader(w http.ResponseWriter, path string) {
	if strings.HasPrefix(path, "/assets/") {
		w.Header().Set("Cache-Control", "public, max-age=31536000, immutable")
		return
	}
	if strings.HasSuffix(path, ".js") || strings.HasSuffix(path, ".css") || strings.HasSuffix(path, ".svg") || strings.HasSuffix(path, ".png") || strings.HasSuffix(path, ".webp") || strings.HasSuffix(path, ".ico") {
		w.Header().Set("Cache-Control", "public, max-age=31536000, immutable")
		return
	}
	w.Header().Set("Cache-Control", "public, max-age=600")
}

func injectSEO(document string, seo SEO, text string) string {
	meta := fmt.Sprintf(`<title>%s</title>
<meta name="description" content="%s">
<meta name="keywords" content="%s">
<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1">
<meta name="theme-color" content="#F8F5FF">
<link rel="canonical" href="%s">
<meta property="og:title" content="%s">
<meta property="og:description" content="%s">
<meta property="og:image" content="%s">
<meta property="og:type" content="website">
<meta property="og:locale" content="zh_CN">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">%s</script>`, html.EscapeString(seo.Title), html.EscapeString(seo.Description), html.EscapeString(seo.Keywords), html.EscapeString(seo.Canonical), html.EscapeString(seo.OgTitle), html.EscapeString(seo.OgDesc), html.EscapeString(seo.OgImage), seo.Schema)
	if strings.Contains(document, "</head>") {
		document = strings.Replace(document, "</head>", meta+"\n</head>", 1)
	}
	fallback := `<noscript><section><h1>` + html.EscapeString(seo.Title) + `</h1><p>` + html.EscapeString(text) + `</p></section></noscript>`
	if strings.Contains(document, `<div id="root"></div>`) {
		document = strings.Replace(document, `<div id="root"></div>`, `<div id="root"></div>`+fallback, 1)
	}
	return document
}

func securityHeaders(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("X-Frame-Options", "SAMEORIGIN")
		w.Header().Set("Referrer-Policy", "strict-origin-when-cross-origin")
		w.Header().Set("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
		next.ServeHTTP(w, r)
	})
}

func defaultSEO(title, desc, path string) SEO {
	keywords := "企业管理系统,CRM系统,合同管理系统,财务管理系统,项目管理系统,OA办公系统,AI工作流,企业一体化管理平台,私有化部署,在线更新"
	return SEO{Title: title, Keywords: keywords, Description: desc, Canonical: buildCanonical(path), OgTitle: title, OgDesc: desc, OgImage: ""}
}

func defaultSiteData() SiteData {
	now := nowString()
	site := SiteConfig{SiteName: "DT 企业智能管理系统", Slogan: "轻奢蓝金未来科技风的一体化企业智能管理平台", Logo: "DT", Favicon: "", Phone: "400-888-2026", Email: "business@dtcall.com", Address: "中国 · 企业数字化服务中心", ICP: "", Domain: defaultPublicDomain, ThemePrimary: "#0D4FBE", SeoTitle: "DT 企业智能管理系统 - CRM、合同、财务、项目、OA 一体化企业管理平台", SeoKeywords: "企业管理系统,CRM系统,合同管理系统,财务管理系统,项目管理系统,OA系统,私有化部署,在线更新,企业一体化平台", SeoDescription: "DT 企业智能管理系统覆盖 CRM、合同、财务、项目、OA、AI 协同、私有化部署与官网更新中心，帮助企业构建统一流程、统一数据和持续升级能力。", OgImage: ""}
	return SiteData{Site: site, Navigation: defaultNavigation(), Pages: defaultPages(now), Products: defaultProducts(now), Solutions: defaultSolutions(now), Cases: defaultCases(now), News: defaultNews(now), Resources: defaultResources(now), FAQs: defaultFAQs(), Releases: defaultReleases(now), Users: defaultUsers(), Roles: defaultRoles(), Logs: []OperationLog{}, UpdatedAt: now, NextLeadID: 1, NextLogID: 1, NextItemID: 1000}
}

func defaultPages(now string) []Page {
	return []Page{
		{ID: 1, Key: "home", Title: "首页", Path: "/", Status: "published", SEO: defaultSEO("DT 企业智能管理系统 - CRM、合同、财务、项目、OA 一体化智能管理平台", "面向通用企业管理客户的一体化企业智能管理平台，打通 CRM、合同、财务、项目、OA、AI 协同、私有化部署与官网更新中心。", "/"), UpdateAt: now, Blocks: []PageBlock{
			{ID: 11, BlockKey: "hero", Title: "企业一体化智能管理平台", Subtitle: "打通 CRM、合同、财务、项目、OA 与 AI 协同，让企业从分散管理走向统一经营。", Content: "DT 企业智能管理系统以统一权限、统一流程、统一数据为基础，帮助企业建立可复制、可追踪、可持续优化的经营管理体系，并支持私有化部署与持续在线升级。", ActionText: "预约产品演示", ActionLink: "/contact", Sort: 1, Status: "published"},
			{ID: 12, BlockKey: "value", Title: "把复杂经营链路收束到同一张管理网络里", Subtitle: "从客户线索到合同回款，从项目交付到组织流程，所有关键节点都能被实时看见。", Content: "通过流程联动、经营看板、AI 智能建议和精细化权限，企业可以减少重复录入、降低沟通成本、提升管理决策速度，并建立面向未来的版本更新与部署能力。", Sort: 2, Status: "published"},
		}},
		{ID: 2, Key: "product", Title: "产品能力", Path: "/product", Status: "published", SEO: defaultSEO("DT 企业智能管理系统产品能力 - CRM 合同 财务 生产 项目 OA AI", "系统展示 DT 在客户关系管理、合同管理、财务管理、生产管理、项目管理、OA 协同、AI 工作流、企业网盘等方面的完整能力。", "/product"), UpdateAt: now, Blocks: []PageBlock{{ID: 21, BlockKey: "overview", Title: "统一产品矩阵", Subtitle: "围绕企业经营全链路建设模块能力", Content: "产品能力页面集中展示 CRM、合同、财务、生产、项目、OA、AI、网盘、安全与移动协同等模块。", Sort: 1, Status: "published"}}},
		{ID: 3, Key: "solutions", Title: "解决方案", Path: "/solutions", Status: "published", SEO: defaultSEO("企业数字化管理解决方案 - 制造 销售 项目 集团管控", "面向制造业、销售型企业、项目型企业与集团组织提供企业数字化管理解决方案，覆盖流程协同、数据决策、成本控制和私有化部署。", "/solutions"), UpdateAt: now, Blocks: []PageBlock{{ID: 31, BlockKey: "overview", Title: "按行业和组织模式落地", Subtitle: "让系统能力匹配真实业务现场", Content: "方案页面展示制造、销售、项目交付和集团管控场景下的落地路径。", Sort: 1, Status: "published"}}},
		{ID: 4, Key: "cases", Title: "客户案例", Path: "/cases", Status: "published", SEO: defaultSEO("DT 企业智能管理系统客户案例 - 企业数字化转型实践", "查看 DT 企业智能管理系统在制造、销售、项目和集团管控场景中的落地案例，了解流程效率提升、回款周期缩短和管理透明度提升成果。", "/cases"), UpdateAt: now, Blocks: []PageBlock{{ID: 41, BlockKey: "overview", Title: "真实业务场景验证", Subtitle: "用案例说明系统如何产生管理价值", Content: "客户案例页面展示不同企业在客户、合同、交付、财务和经营看板方面的实践成果。", Sort: 1, Status: "published"}}},
		{ID: 5, Key: "news", Title: "新闻动态", Path: "/news", Status: "published", SEO: defaultSEO("企业管理系统新闻动态与产品更新 - DT 官网", "关注 DT 企业智能管理系统产品更新、行业观点、AI 工作流能力演进和企业数字化管理实践。", "/news"), UpdateAt: now, Blocks: []PageBlock{{ID: 51, BlockKey: "overview", Title: "产品动态与数字化管理洞察", Subtitle: "持续沉淀企业管理系统建设经验", Content: "新闻动态页面汇总产品能力演进、行业方法论和客户部署经验。", Sort: 1, Status: "published"}}},
		{ID: 6, Key: "resources", Title: "帮助与资源", Path: "/resources", Status: "published", SEO: defaultSEO("企业管理系统资源中心 - 白皮书 手册 FAQ 部署说明", "获取 DT 企业智能管理系统白皮书、产品手册、部署说明和常见问题，帮助企业更快完成数字化管理选型。", "/resources"), UpdateAt: now, Blocks: []PageBlock{{ID: 61, BlockKey: "overview", Title: "资料、手册与常见问题", Subtitle: "帮助客户更快完成选型与部署", Content: "资源中心提供白皮书、产品手册、部署说明与 FAQ，所有内容均可在后台维护。", Sort: 1, Status: "published"}}},
		{ID: 7, Key: "updates", Title: "版本更新", Path: "/updates", Status: "published", SEO: defaultSEO("DT 企业管理系统版本更新发布 - 客户部署升级包", "通过官网发布 DT 企业管理系统版本更新、升级包下载地址、校验信息、目标环境和升级说明，服务客户部署系统持续升级。", "/updates"), UpdateAt: now, Blocks: []PageBlock{{ID: 71, BlockKey: "overview", Title: "DT 企业管理系统版本发布中心", Subtitle: "这里发布客户部署系统的升级包与版本说明", Content: "版本更新页面面向已部署客户提供版本号、目标环境、升级说明、下载地址和校验信息。", Sort: 1, Status: "published"}}},
		{ID: 8, Key: "contact", Title: "联系我们", Path: "/contact", Status: "published", SEO: defaultSEO("联系 DT 企业智能管理系统 - 预约演示 获取方案", "联系 DT 企业智能管理系统商务团队，预约产品演示、获取行业方案、咨询私有化部署与企业数字化升级路径。", "/contact"), UpdateAt: now, Blocks: []PageBlock{{ID: 81, BlockKey: "overview", Title: "统一联系方式", Subtitle: "电话、邮箱、地址与域名均由后台站点配置集中维护", Content: "客户可以通过表单提交咨询，也可以直接拨打电话或发送邮件。", Sort: 1, Status: "published"}}},
	}
}

func defaultNavigation() []NavigationItem {
	return []NavigationItem{{ID: 1, Title: "首页", Path: "/", Position: "header", Target: "_self", Sort: 1, Enabled: true}, {ID: 2, Title: "产品能力", Path: "/product", Position: "header", Target: "_self", Sort: 2, Enabled: true}, {ID: 3, Title: "解决方案", Path: "/solutions", Position: "header", Target: "_self", Sort: 3, Enabled: true}, {ID: 4, Title: "客户案例", Path: "/cases", Position: "header", Target: "_self", Sort: 4, Enabled: true}, {ID: 5, Title: "新闻动态", Path: "/news", Position: "header", Target: "_self", Sort: 5, Enabled: true}, {ID: 6, Title: "帮助资源", Path: "/resources", Position: "header", Target: "_self", Sort: 6, Enabled: true}, {ID: 7, Title: "更新中心", Path: "/updates", Position: "header", Target: "_self", Sort: 7, Enabled: true}, {ID: 8, Title: "联系我们", Path: "/contact", Position: "header", Target: "_self", Sort: 8, Enabled: true}}
}

func defaultProducts(now string) []Product {
	return []Product{
		{ID: 101, Title: "客户与销售 CRM", Slug: "crm", Icon: "spark", Summary: "线索、客户、商机、跟进、回款全流程管理", Description: "帮助销售团队建立从线索获取到成交回款的标准化管理体系，提升客户沉淀与转化效率。", Features: []string{"客户公海与私海", "跟进记录与提醒", "商机阶段推进", "销售数据看板"}, Metrics: []Metric{{Label: "线索响应", Value: "快 60%"}, {Label: "客户沉淀", Value: "统一"}}, Sort: 1, Status: "published", UpdatedAt: now, SEO: defaultSEO("CRM客户关系管理系统 - DT 企业智能管理系统", "DT CRM 覆盖线索、客户、商机、跟进、回款和销售看板，帮助企业提升客户转化效率和销售管理透明度。", "/product#crm")},
		{ID: 102, Title: "合同与财务协同", Slug: "contract-finance", Icon: "contract", Summary: "合同审批、收付款、发票、费用与利润联动", Description: "把合同履约、财务收支和业务进展连接起来，让经营数据实时准确。", Features: []string{"合同全生命周期", "回款计划", "费用审批", "利润分析"}, Metrics: []Metric{{Label: "回款周期", Value: "缩短"}, {Label: "财务对账", Value: "自动"}}, Sort: 2, Status: "published", UpdatedAt: now, SEO: defaultSEO("合同管理与财务管理系统 - DT 企业智能管理系统", "DT 合同与财务协同能力覆盖合同审批、回款计划、费用报销、发票管理和利润分析，提升企业经营管控能力。", "/product#contract-finance")},
		{ID: 103, Title: "生产与项目交付", Slug: "production-project", Icon: "factory", Summary: "生产任务、项目计划、进度节点和交付风险统一管控", Description: "面向制造和项目型业务，统一生产排期、任务协作、项目节点和风险预警。", Features: []string{"生产任务排期", "项目里程碑", "进度追踪", "风险预警"}, Metrics: []Metric{{Label: "交付可视", Value: "全程"}, {Label: "异常预警", Value: "实时"}}, Sort: 3, Status: "published", UpdatedAt: now, SEO: defaultSEO("生产管理与项目管理系统 - DT 企业智能管理系统", "DT 生产与项目管理能力支持任务排期、项目里程碑、交付进度、异常预警和复盘分析，提升企业交付效率。", "/product#production-project")},
		{ID: 104, Title: "AI 工作流与知识库", Slug: "ai-workflow", Icon: "ai", Summary: "让 AI 理解业务意图，辅助流程、内容、销售与合规", Description: "基于业务数据与知识库构建智能助手，辅助员工完成流程判断、内容生成和经营分析。", Features: []string{"意图识别", "知识库问答", "智能销售建议", "合规检查"}, Metrics: []Metric{{Label: "重复工作", Value: "减少"}, {Label: "智能辅助", Value: "随时"}}, Sort: 4, Status: "published", UpdatedAt: now, SEO: defaultSEO("AI工作流与企业知识库 - DT 企业智能管理系统", "DT AI 工作流结合企业知识库、意图识别、销售建议和合规检查，帮助企业构建更智能的业务协同体系。", "/product#ai-workflow")},
		{ID: 105, Title: "OA 审批与组织协同", Slug: "oa-collaboration", Icon: "workflow", Summary: "请假、报销、采购、用印、合同等审批统一流转", Description: "围绕组织、角色和权限构建标准审批流程，减少线下沟通与重复确认。", Features: []string{"流程表单", "条件审批", "移动处理", "审批留痕"}, Metrics: []Metric{{Label: "流程效率", Value: "提升"}, {Label: "审批记录", Value: "可追溯"}}, Sort: 5, Status: "published", UpdatedAt: now, SEO: defaultSEO("OA审批协同系统 - DT 企业智能管理系统", "DT OA 审批协同支持流程表单、条件审批、移动处理和审批留痕，帮助企业提升组织协作效率。", "/product#oa-collaboration")},
		{ID: 106, Title: "企业网盘与文档中心", Slug: "enterprise-drive", Icon: "cloud", Summary: "项目资料、合同附件、知识文档和版本文件统一沉淀", Description: "把业务文档与客户、合同、项目、流程关联，形成安全可控的企业知识资产。", Features: []string{"权限分级", "资料归档", "在线预览", "关联业务"}, Metrics: []Metric{{Label: "资料查找", Value: "更快"}, {Label: "文档安全", Value: "可控"}}, Sort: 6, Status: "published", UpdatedAt: now, SEO: defaultSEO("企业网盘与文档管理 - DT 企业智能管理系统", "DT 企业网盘支持项目资料、合同附件、知识文档和版本文件统一管理，沉淀企业知识资产。", "/product#enterprise-drive")},
		{ID: 107, Title: "经营数据看板", Slug: "business-dashboard", Icon: "chart", Summary: "销售、合同、回款、成本、项目和生产指标实时展示", Description: "统一核心经营数据口径，帮助管理层更快发现异常并制定策略。", Features: []string{"多维报表", "指标预警", "趋势分析", "权限看板"}, Metrics: []Metric{{Label: "数据口径", Value: "统一"}, {Label: "决策速度", Value: "更快"}}, Sort: 7, Status: "published", UpdatedAt: now, SEO: defaultSEO("企业经营数据看板 - DT 企业智能管理系统", "DT 经营数据看板统一销售、合同、回款、成本、项目和生产指标，提升企业经营决策效率。", "/product#business-dashboard")},
		{ID: 108, Title: "权限安全与私有化部署", Slug: "security-deployment", Icon: "shield", Summary: "角色权限、审计日志、数据隔离与客户现场部署能力", Description: "满足企业对数据安全、内网部署、权限隔离和操作追踪的要求。", Features: []string{"角色权限", "操作审计", "内网部署", "数据隔离"}, Metrics: []Metric{{Label: "安全边界", Value: "清晰"}, {Label: "部署模式", Value: "灵活"}}, Sort: 8, Status: "published", UpdatedAt: now, SEO: defaultSEO("私有化部署与权限安全 - DT 企业智能管理系统", "DT 支持角色权限、操作审计、数据隔离和私有化部署，满足企业安全可控的管理系统建设要求。", "/product#security-deployment")},
	}
}

func defaultSolutions(now string) []ContentItem {
	return []ContentItem{
		{ID: 201, Type: "solution", Title: "制造企业全流程数字化管理方案", Slug: "manufacturing-digital-management", Category: "制造业", Cover: "", Summary: "贯通销售、合同、采购、生产、质检、交付和财务，提升制造企业计划协同与交付透明度。", Content: "制造企业常见痛点在于订单、生产、库存、财务数据割裂。DT 通过客户订单、合同回款、生产排期和项目交付联动，让管理层实时掌握经营状态。", Tags: []string{"制造业", "生产管理", "合同财务"}, Status: "published", Recommended: true, PublishedAt: now, UpdatedAt: now, SEO: defaultSEO("制造企业数字化管理方案 - 生产 合同 财务 CRM 一体化", "DT 制造企业数字化管理方案打通 CRM、合同、财务、生产和项目交付，帮助制造企业提升计划协同、交付效率和经营透明度。", "/solutions/manufacturing-digital-management")},
		{ID: 202, Type: "solution", Title: "销售型企业增长管理方案", Slug: "sales-growth-management", Category: "销售型企业", Cover: "", Summary: "用标准化 CRM、商机推进和回款看板提升销售团队协作效率。", Content: "销售型企业需要更快响应线索、更准确预测回款、更稳定沉淀客户资产。DT 将销售流程、合同、财务和 AI 建议组合起来，构建增长管理闭环。", Tags: []string{"CRM", "销售管理", "增长"}, Status: "published", Recommended: true, PublishedAt: now, UpdatedAt: now, SEO: defaultSEO("销售型企业 CRM 增长管理方案 - 线索 商机 回款", "DT 销售增长管理方案覆盖线索分配、客户跟进、商机阶段、合同回款和销售预测，帮助销售团队提升转化率。", "/solutions/sales-growth-management")},
		{ID: 203, Type: "solution", Title: "项目型企业交付管控方案", Slug: "project-delivery-control", Category: "项目型企业", Cover: "", Summary: "项目计划、任务协作、成本费用、客户沟通和交付验收统一管理。", Content: "项目型企业需要让每个节点可追踪、每项成本可核算、每次交付可复盘。DT 通过项目、合同、财务、文档和 OA 流程联动降低交付风险。", Tags: []string{"项目管理", "交付", "成本"}, Status: "published", Recommended: false, PublishedAt: now, UpdatedAt: now, SEO: defaultSEO("项目型企业交付管控方案 - 项目管理 成本 进度 风险", "DT 项目交付管控方案覆盖项目计划、任务协同、成本费用、合同回款和交付验收，帮助项目型企业降低风险。", "/solutions/project-delivery-control")},
	}
}

func defaultCases(now string) []ContentItem {
	return []ContentItem{
		{ID: 301, Type: "case", Title: "某装备制造企业实现订单到交付全过程透明", Slug: "equipment-manufacturing-case", Category: "装备制造", Cover: "", Summary: "通过 CRM、合同、生产和项目联动，企业实现订单进度可视、回款节点清晰、交付风险提前预警。", Content: "客户原先依赖表格和人工会议同步订单进度。上线 DT 后，销售订单、合同回款、生产任务和交付节点统一展示，管理层可实时查看异常和关键指标。", Tags: []string{"制造业", "生产管理", "交付"}, Status: "published", Recommended: true, PublishedAt: now, UpdatedAt: now, SEO: defaultSEO("装备制造企业数字化转型案例 - DT 企业智能管理系统", "某装备制造企业使用 DT 打通 CRM、合同、生产和项目交付，实现订单全过程透明、回款节点清晰和风险提前预警。", "/cases/equipment-manufacturing-case")},
		{ID: 302, Type: "case", Title: "某服务集团搭建统一客户与项目运营中台", Slug: "service-group-operation-case", Category: "集团服务", Cover: "", Summary: "集团总部统一管理客户资产、项目进度、合同回款和知识文档，提升跨部门协同效率。", Content: "该集团存在多团队客户数据分散、项目交付状态不透明的问题。DT 通过统一客户库、项目流程、合同财务和企业网盘完成运营中台建设。", Tags: []string{"集团管控", "客户资产", "项目运营"}, Status: "published", Recommended: true, PublishedAt: now, UpdatedAt: now, SEO: defaultSEO("集团客户与项目运营中台案例 - DT 企业智能管理系统", "某服务集团使用 DT 建设统一客户与项目运营中台，实现客户资产沉淀、项目进度透明和合同回款协同。", "/cases/service-group-operation-case")},
	}
}

func defaultNews(now string) []ContentItem {
	return []ContentItem{
		{ID: 401, Type: "news", Title: "DT 企业智能管理系统发布 AI 工作流增强能力", Slug: "ai-workflow-upgrade", Category: "产品更新", Cover: "", Summary: "新版 AI 工作流支持业务意图识别、知识库问答和销售策略建议，帮助企业减少重复性管理工作。", Content: "本次更新聚焦企业管理场景中的智能辅助能力，围绕线索分析、流程建议、知识问答和合规提醒增强 AI 对业务上下文的理解。", Tags: []string{"AI工作流", "产品更新"}, Status: "published", Recommended: true, PublishedAt: now, UpdatedAt: now, SEO: defaultSEO("DT AI 工作流增强能力发布 - 企业管理系统产品更新", "DT 企业智能管理系统发布 AI 工作流增强能力，支持业务意图识别、知识库问答、销售策略建议和合规检查。", "/news/ai-workflow-upgrade")},
		{ID: 402, Type: "news", Title: "企业为什么需要一体化管理系统而不是更多孤立工具", Slug: "integrated-management-system-value", Category: "行业观点", Cover: "", Summary: "当业务工具越来越多，真正稀缺的是统一数据、统一流程和统一决策视图。", Content: "孤立工具会造成重复录入、数据口径不一致和协同成本升高。一体化管理系统的价值在于把关键业务流程组织到同一个数据网络中。", Tags: []string{"企业管理", "数字化转型"}, Status: "published", Recommended: true, PublishedAt: now, UpdatedAt: now, SEO: defaultSEO("企业一体化管理系统价值 - 为什么不能只依赖孤立工具", "企业需要一体化管理系统来统一数据、流程和决策视图，避免 CRM、合同、财务、生产、项目等工具孤立带来的管理成本。", "/news/integrated-management-system-value")},
		{ID: 403, Type: "news", Title: "从合同回款看企业经营数字化闭环", Slug: "contract-payment-digital-loop", Category: "管理洞察", Cover: "", Summary: "合同、回款、发票、费用与项目成本联动后，企业才能形成真正可追踪的经营闭环。", Content: "经营数字化不是单独上线一个合同工具，而是让合同金额、履约节点、回款计划、费用支出和项目交付同频更新。", Tags: []string{"合同管理", "财务协同"}, Status: "published", Recommended: true, PublishedAt: now, UpdatedAt: now, SEO: defaultSEO("合同回款与企业经营数字化闭环 - DT 管理洞察", "通过合同、回款、发票、费用和项目成本联动，企业可以建立经营数字化闭环，提高利润分析和风险预警能力。", "/news/contract-payment-digital-loop")},
	}
}

func defaultResources(now string) []Resource {
	return []Resource{{ID: 501, Title: "企业一体化管理系统选型白皮书", Slug: "management-system-whitepaper", Category: "白皮书", Summary: "从业务流程、数据中台、权限安全、部署模式和长期扩展性评估企业管理系统。", FileURL: "", NeedLead: true, Tags: []string{"选型", "白皮书"}, Status: "published", PublishedAt: now, SEO: defaultSEO("企业一体化管理系统选型白皮书 - DT 资源中心", "下载企业一体化管理系统选型白皮书，了解 CRM、合同、财务、生产、项目、OA 和 AI 工作流系统选型方法。", "/resources")}, {ID: 502, Title: "DT 企业智能管理系统功能手册", Slug: "product-manual", Category: "产品手册", Summary: "快速了解 DT 在 CRM、合同、财务、生产、项目、OA、AI 工作流和企业网盘方面的核心能力。", FileURL: "", NeedLead: false, Tags: []string{"产品手册", "功能"}, Status: "published", PublishedAt: now, SEO: defaultSEO("DT 企业智能管理系统功能手册 - CRM 合同 财务 生产 项目 OA", "DT 企业智能管理系统功能手册介绍 CRM、合同、财务、生产、项目、OA、AI 工作流和企业网盘核心能力。", "/resources")}}
}

func defaultFAQs() []FAQ {
	return []FAQ{{ID: 601, Question: "DT 企业智能管理系统支持私有化部署吗？", Answer: "支持。系统可根据企业安全、合规和网络环境要求进行私有化部署，并可结合企业现有组织架构和权限体系配置。", Category: "部署", Sort: 1, Status: "published"}, {ID: 602, Question: "DT 企业管理系统版本更新如何发布给客户？", Answer: "官网版本更新中心用于发布客户已部署 DT 企业管理系统的版本号、升级包地址、校验码、目标环境和升级说明，客户可据此安全获取更新。", Category: "版本更新", Sort: 2, Status: "published"}, {ID: 603, Question: "系统适合哪些企业？", Answer: "适合需要统一管理客户、合同、财务、生产、项目、OA、知识文档和 AI 工作流的成长型企业、制造企业、项目型企业与集团组织。", Category: "产品", Sort: 3, Status: "published"}}
}

func defaultReleases(now string) []Release {
	return []Release{
		{ID: 701, Version: "1.0.0", Title: "DT 企业管理系统 1.0.0 稳定版", Summary: "Linux Docker Compose 首个标准化离线发布版本，支持官网更新中心检测、Docker ZIP 升级包和版本目录切换。", PackageURL: "", Checksum: "", ChecksumType: "sha256", ManifestURL: "", Target: "Ubuntu 22.04 x86_64 / Docker Compose", Channel: "stable", Platform: "linux-docker-x64", Build: "20260701.1", PackageSize: 0, MinSupportedVersion: "1.0.0", ForceUpdate: false, DockerImageTags: []string{"dtcall-web:1.0.0", "dtcall-ai-orchestrator:1.0.0"}, ReleaseNotesMarkdown: "- 首次提供官网更新中心\n- 支持 Docker ZIP 离线升级包\n- 支持版本目录切换和回滚", Status: "published", PublishedAt: now, UpdatedAt: now, Highlights: []string{"官网统一版本检测", "Docker 离线更新包", "版本目录切换与回滚"}},
	}
}

func defaultUsers() []AdminUser {
	return []AdminUser{}
}

func defaultRoles() []Role {
	return []Role{{ID: 1, Name: "系统管理员", Permissions: []string{"dashboard", "site", "content", "releases", "leads", "seo", "users", "logs", "backups"}, CreatedAt: nowString()}, {ID: 2, Name: "内容运营", Permissions: []string{"dashboard", "site", "content", "releases", "seo"}, CreatedAt: nowString()}, {ID: 3, Name: "销售人员", Permissions: []string{"dashboard", "leads"}, CreatedAt: nowString()}}
}
