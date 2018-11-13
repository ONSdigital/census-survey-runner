package main

import (
    "fmt"
    "time"
    "html/template"
    "log"
    "net/http"
    "os"
    "context"
    "strings"
    "path/filepath"
    "strconv"
    "encoding/json"
    "io/ioutil"
    "github.com/satori/go.uuid"
    "cloud.google.com/go/storage"
    "crypto/aes"
    "crypto/sha256"
    "crypto/rand"
    "crypto/cipher"
    "golang.org/x/crypto/pbkdf2"
)

type MembersData struct {
    AddressLine1 string
    Members []string
}

type MemberData struct {
    FirstName string
    MiddleNames string
    LastName string
}

type VisitorData struct {
    VisitorNumber int
}

type AnswerData struct {
    AnswerId string
    AnswerInstance int
    GroupInstance int
    Value string
}

var ctx = context.Background()

var storage_backend = os.Getenv("EQ_STORAGE_BACKEND")

var gcs_bucket = getGcsBucket()

var pages = parseTemplates()

var local_storage = map[string][]byte{}

var SALT = []byte("this-a-a-dev-salt-only-for-testing")

var MEMBERS_PAGES = []string{
    "introduction",
    "permanent-or-family-home",
    "household-composition",
    "everyone-at-address-confirmation",
    "overnight-visitors",
    "household-relationships",
    "completed",
}

var HOUSEHOLD_PAGES = []string{
    "introduction",
    "type-of-accommodation",
    "type-of-house",
    "self-contained-accommodation",
    "number-of-bedrooms",
    "central-heating",
    "own-or-rent",
    "number-of-vehicles",
    "completed",
}

var MEMBER_PAGES = []string{
    "introduction",
    "details-correct",
    "over-16",
    "private-response",
    "sex",
    "date-of-birth",
    "marital-status",
    "another-address",
    "other-address",
    "address-type",
    "in-education",
    "term-time-location",
    "country-of-birth",
    "carer",
    "national-identity",
    "ethnic-group",
    "other-ethnic-group",
    "language",
    "religion",
    "past-usual-address",
    "passports",
    "disability",
    "qualifications",
    "employment-type",
    "jobseeker",
    "job-availability",
    "job-pending",
    "occupation",
    "ever-worked",
    "main-job",
    "hours-worked",
    "work-travel",
    "job-title",
    "job-description",
    "main-job-type",
    "business-name",
    "employers-business",
    "completed",
}

var VISITOR_PAGES = []string{
    "name",
    "sex",
    "date-of-birth",
    "uk-resident",
    "address",
    "completed",
}

func handleSession(w http.ResponseWriter, r *http.Request) {
    // TODO decode/validate JTI

    user_id := uuid.Must(uuid.NewV4())
    user_ik := uuid.Must(uuid.NewV4())

    expiration := time.Now().Add(time.Hour)
    http.SetCookie(w, &http.Cookie{Name: "user_id", Value: user_id.String(), Expires: expiration})
    http.SetCookie(w, &http.Cookie{Name: "user_ik", Value: user_ik.String(), Expires: expiration})

    redirect(w, r, "/introduction")
}

func handleIntroduction(w http.ResponseWriter, r *http.Request) {
    if r.Method == http.MethodPost {
        answers := parseAnswers(r, 0)
        updateAnswers(r, answers)
        redirect(w, r, "/address")
        return
    }

    pages.ExecuteTemplate(w, "introduction", "")
}

func handleAddress(w http.ResponseWriter, r *http.Request) {
    if r.Method == http.MethodPost {
        answers := parseAnswers(r, 0)
        updateAnswers(r, answers)
        redirect(w, r, "/members/introduction")
        return
    }

    pages.ExecuteTemplate(w, "address", "")
}

func handleMembers(w http.ResponseWriter, r *http.Request) {
    page := r.URL.Path[len("/members/"):]

    if r.Method == http.MethodPost {
        var answers map[string]string
        if page == "household-composition" {
            answers = map[string]string{}
            r.ParseForm()
            for k, v := range r.Form {
                if k[:10] == "household-" {
                    parts := strings.SplitN(k, "-", 3)
                    answer_instance, _ := strconv.Atoi(parts[1])
                    answers[ak(parts[2], answer_instance, 0)] = v[0]
                }
            }
        } else if page == "household-relationships" {
            answers = map[string]string{}
            r.ParseForm()
            for k, v := range r.Form {
                if len(k) > 31 && k[:31] == "household-relationships-answer-" {
                    answer_instance, _ := strconv.Atoi(k[31:])
                    answers[ak("household-relationships-answer", answer_instance, 0)] = v[0]
                }
            }
        } else {
            answers = parseAnswers(r, 0)
        }

        updateAnswers(r, answers)

        i := index(MEMBERS_PAGES, page) + 1

        next := "/household/introduction"
        if i < len(MEMBERS_PAGES) {
            next = "/members/" + MEMBERS_PAGES[i]
        }

        redirect(w, r, next)
        return
    }

    user_id, _ := r.Cookie("user_id")
    storage_key := makeKey(r)
    getAnswers(user_id.Value, storage_key)

    data := MembersData{ // TODO
        AddressLine1: "44 hill side",
        Members: []string{
            "Danny K Boje",
            "Anjali M Yo",
        },
    }
    pages.ExecuteTemplate(w, "members/" + page, data)
}

func handleHousehold(w http.ResponseWriter, r *http.Request) {
    page := r.URL.Path[len("/household/"):]

    if r.Method == http.MethodPost {
        answers := parseAnswers(r, 0)
        updateAnswers(r, answers)

        i := index(HOUSEHOLD_PAGES, page) + 1

        next := "/member/0/introduction"
        if i < len(HOUSEHOLD_PAGES) {
            next = "/household/" + HOUSEHOLD_PAGES[i]
        }

        redirect(w, r, next)
        return
    }

    pages.ExecuteTemplate(w, "household/" + page, "")
}

func handleMember(w http.ResponseWriter, r *http.Request) {
    parts := strings.Split(r.URL.Path, "/")
    group_instance, _ := strconv.Atoi(parts[2])
    page := parts[3]

    if r.Method == http.MethodPost {
        var answers map[string]string
        if page == "date-of-birth" {
            answers = parseDate(r, "date-of-birth-answer", group_instance)
        } else {
            answers = parseAnswers(r, group_instance)
        }

        updateAnswers(r, answers)

        if page == "private-response" {
            if r.FormValue("private-response-answer")[:3] == "Yes" {
                redirect(w, r, fmt.Sprintf("/member/%v/request-private-response", group_instance))
                return
            }
        }

        if page == "request-private-response" {
            redirect(w, r, fmt.Sprintf("/member/%v/completed", group_instance))
            return
        }

        num_members := 2 // TODO

        i := index(MEMBER_PAGES, page) + 1

        next := "/visitors_introduction"
        if i < len(MEMBER_PAGES) {
            next = fmt.Sprintf("/member/%v/%v", group_instance, MEMBER_PAGES[i])
        } else if group_instance + 1 < num_members {
            next = fmt.Sprintf("/member/%v/introduction", (group_instance + 1))
        }

        redirect(w, r, next)
        return
    }

    user_id, _ := r.Cookie("user_id")
    storage_key := makeKey(r)
    getAnswers(user_id.Value, storage_key)

    data := MemberData{ // TODO
        FirstName: "Danny",
        MiddleNames: "K",
        LastName: "Boje",
    }
    if group_instance == 1 {
        data = MemberData{
            FirstName: "Anjali",
            MiddleNames: "M",
            LastName: "Yo",
        }
    }
    pages.ExecuteTemplate(w, "member/" + page, data)
}

func handleVisitorsIntroduction(w http.ResponseWriter, r *http.Request) {
    if r.Method == http.MethodPost {
        answers := parseAnswers(r, 0)
        updateAnswers(r, answers)
        redirect(w, r, "/visitor/0/name")
        return
    }

    pages.ExecuteTemplate(w, "visitors_introduction", "")
}

func handleVisitor(w http.ResponseWriter, r *http.Request) {
    parts := strings.Split(r.URL.Path, "/")
    group_instance, _ := strconv.Atoi(parts[2])
    page := parts[3]

    if r.Method == http.MethodPost {
        var answers map[string]string
        if page == "date-of-birth" {
            answers = parseDate(r, "visitor-date-of-birth-answer", group_instance)
        } else {
            answers = parseAnswers(r, group_instance)
        }

        updateAnswers(r, answers)

        num_visitors := 2 // TODO

        i := index(VISITOR_PAGES, page) + 1

        next := "/visitors_completed"
        if i < len(VISITOR_PAGES) {
            next = fmt.Sprintf("/visitor/%v/%v", group_instance, VISITOR_PAGES[i])
        } else if group_instance + 1 < num_visitors {
            next = fmt.Sprintf("/visitor/%v/name", (group_instance + 1))
        }

        redirect(w, r, next)
        return
    }

    data := VisitorData{
        VisitorNumber: group_instance + 1,
    }
    pages.ExecuteTemplate(w, "visitor/" + page, data)
}

func handleVisitorsCompleted(w http.ResponseWriter, r *http.Request) {
    if r.Method == http.MethodPost {
        answers := parseAnswers(r, 0)
        updateAnswers(r, answers)
        redirect(w, r, "/completed")
        return
    }

    pages.ExecuteTemplate(w, "visitors_completed", "")
}

func handleCompleted(w http.ResponseWriter, r *http.Request) {
    if r.Method == http.MethodPost {
        // TODO validate and submit answers
        log.Print("Submitting answers")
        redirect(w, r, "/thank-you")
        return
    }

    pages.ExecuteTemplate(w, "completed", "")
}

func handleThankYou(w http.ResponseWriter, r *http.Request) {
    pages.ExecuteTemplate(w, "thank-you", "")
}

func handleSubmission(w http.ResponseWriter, r *http.Request) {
    user_id, _ := r.Cookie("user_id")
    storage_key := makeKey(r)
    answers, _ := getAnswers(user_id.Value, storage_key)
    flat_answers := []AnswerData{}

    for k, v := range answers {
        parts := strings.SplitN(k, ":", 3)
        answer_instance, _ := strconv.Atoi(parts[1])
        group_instance, _ := strconv.Atoi(parts[2])
        flat_answers = append(flat_answers, AnswerData{
            AnswerId: parts[0],
            AnswerInstance: answer_instance,
            GroupInstance: group_instance,
            Value: v,
        })
    }

    json.NewEncoder(w).Encode(flat_answers)
}

func handleStatus(w http.ResponseWriter, r *http.Request) {
    fmt.Fprint(w, "OK")
}

func index(slice []string, item string) int {
    for i, _ := range slice {
        if slice[i] == item {
            return i
        }
    }
    return -1
}

func redirect(w http.ResponseWriter, r *http.Request, path string) {
    http.Redirect(w, r, "http://" + r.Host + path, http.StatusFound)
}

func makeKey(r *http.Request) []byte {
    user_id, _ := r.Cookie("user_id")
    user_ik, _ := r.Cookie("user_ik")
	return pbkdf2.Key([]byte(user_id.Value + user_ik.Value), SALT, 1000, 32, sha256.New)
}

func encryptData(key []byte, answers map[string]string) []byte {
    data, _ := json.Marshal(answers)
	iv := make([]byte, 12)
	rand.Read(iv)
	b, _ := aes.NewCipher(key)
	aesgcm, _ := cipher.NewGCM(b)
	return append(iv, aesgcm.Seal(nil, iv, data, nil)...)
}

func decryptData(key []byte, data []byte) map[string]string {
	b, _ := aes.NewCipher(key)
	aesgcm, _ := cipher.NewGCM(b)
	decrypted, _ := aesgcm.Open(nil, data[:12], data[12:], nil)

	var answers map[string]string
	json.Unmarshal(decrypted, &answers)
	return answers
}

func getAnswers(user_id string, key []byte) (map[string]string, error) {
    if storage_backend == "gcs" {
        rc, err := gcs_bucket.Object("go/" + user_id).NewReader(ctx)
        if err != nil {
            if err.Error() == "storage: object doesn't exist" {
                return map[string]string{}, nil
            } else {
                return nil, err
            }
        }
        defer rc.Close()

        encrypted, _ := ioutil.ReadAll(rc)
        return decryptData(key, encrypted), nil
    } else {
        if val, ok := local_storage[user_id]; ok {
            return decryptData(key, val), nil
        }
        return map[string]string{}, nil
    }
}

func putAnswers(user_id string, answers map[string]string, key []byte) error {
    if storage_backend == "gcs" {
        wc := gcs_bucket.Object("go/" + user_id).NewWriter(ctx)

        wc.Write(encryptData(key, answers))

        if err := wc.Close(); err != nil {
            return err
        }

        return nil
    } else {
        local_storage[user_id] = encryptData(key, answers)

        return nil
    }
}

func updateAnswers(r *http.Request, new_answers map[string]string) map[string]string {
    user_id, _ := r.Cookie("user_id")
    storage_key := makeKey(r)
    answers, _ := getAnswers(user_id.Value, storage_key)

    for k, v := range new_answers {
        answers[k] = v
    }

    putAnswers(user_id.Value, answers, storage_key)
    return answers
}

func ak(answer_id string, answer_instance int, group_instance int) string {
    return fmt.Sprintf("%v:%v:%v", answer_id, answer_instance, group_instance)
}

func parseDate(r *http.Request, answer_id string, group_instance int) map[string]string {
    r.ParseForm()
    year, _ := strconv.Atoi(r.Form[answer_id + "-year"][0])
    month, _ := strconv.Atoi(r.Form[answer_id + "-month"][0])
    day, _ := strconv.Atoi(r.Form[answer_id + "-day"][0])
    value := fmt.Sprintf("%04d-%02d-%02d", year, month, day)

    return map[string]string{ak(answer_id, 0, group_instance): value}
}

func parseAnswers(r *http.Request, group_instance int) map[string]string {
    // TODO csrf
    r.ParseForm()

    var answers = map[string]string{}
    for k, vs := range r.Form {
        if k != "csrf_token" && k[:6] != "action" {
            // TODO ints and lists
            answers[ak(k, 0, group_instance)] = strings.Join(vs, ",")
        }
    }

    return answers
}

func parseTemplates() *template.Template {
    templ := template.New("")
    err := filepath.Walk("./flat_templates", func(path string, info os.FileInfo, err error) error {
        if strings.Contains(path, ".html") {
            _, err = templ.ParseFiles(path)
            if err != nil {
                log.Println(err)
            }
        }

        return err
    })

    if err != nil {
        panic(err)
    }

    return templ
}

func getGcsBucket() *storage.BucketHandle {
    if storage_backend != "gcs" {
        return nil
    }

    max_conns_per_host := 30
    max_conns_per_host_str := os.Getenv("EQ_GCS_MAX_POOL_CONNECTIONS")
    if max_conns_per_host_str != "" {
        max_conns_per_host, _ = strconv.Atoi(max_conns_per_host_str)
    }
    // TODO don't do this globally
    http.DefaultTransport.(*http.Transport).MaxIdleConnsPerHost = max_conns_per_host

    client, err := storage.NewClient(ctx)
    if err != nil {
            log.Fatalf("Failed to create client: %v", err)
    }

    return client.Bucket(os.Getenv("EQ_GCS_BUCKET_ID"))
}

func main() {
    fs := http.FileServer(http.Dir("static"))
    http.Handle("/static/", http.StripPrefix("/static/", fs))
    http.HandleFunc("/session", handleSession)
    http.HandleFunc("/introduction", handleIntroduction)
    http.HandleFunc("/address", handleAddress)
    http.HandleFunc("/members/", handleMembers)
    http.HandleFunc("/household/", handleHousehold)
    http.HandleFunc("/member/", handleMember)
    http.HandleFunc("/visitors_introduction", handleVisitorsIntroduction)
    http.HandleFunc("/visitor/", handleVisitor)
    http.HandleFunc("/visitors_completed", handleVisitorsCompleted)
    http.HandleFunc("/completed", handleCompleted)
    http.HandleFunc("/thank-you", handleThankYou)
    http.HandleFunc("/dump/submission", handleSubmission)
    http.HandleFunc("/status", handleStatus)
    log.Fatal(http.ListenAndServe(":5000", nil))
}
