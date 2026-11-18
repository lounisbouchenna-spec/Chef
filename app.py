import streamlit as st
from groq import Groq
from PIL import Image
import base64
import io
import urllib.parse

st.set_page_config(page_title="Mon Chef IA", page_icon="🍳", layout="centered")
st.title("🍳 Mon Chef & Chasseur de Promos")

if "recettes_sauvegardees" not in st.session_state:
    st.session_state.recettes_sauvegardees = []

if "derniere_recette" not in st.session_state:
    st.session_state.derniere_recette = None

if "GROQ_API_KEY" not in st.secrets:
    st.error("⚠️ Clé API Groq manquante. Ajoutez GROQ_API_KEY dans les Secrets de Streamlit.")
    st.stop()

client = Groq(api_key=st.secrets["GROQ_API_KEY"])

def encode_image(image_file):
    img = Image.open(image_file)
    img.thumbnail((768, 768))
    buffer = io.BytesIO()
    img.convert("RGB").save(buffer, format="JPEG", quality=80)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

# Déclaration des onglets sans crochets
tab_creer, tab_favoris = st.tabs(["👨‍🍳 Créer une recette", f"❤️ Mes recettes ({len(st.session_state.recettes_sauvegardees)})"])

# ==========================================
# ONGLET 1 : CRÉATION ET RECHERCHE DE PROMOS
# ==========================================
with tab_creer:
    ville = st.text_input("📍 Votre ville (pour les promos autour de vous)", placeholder="Ex: Lyon, Bordeaux, Lille...")

    st.subheader("🥗 Vos préférences")
    col1, col2 = st.columns(2)
    with col1:
        regime = st.selectbox(
            "Régime alimentaire",
            ("Classique (Tout)", "Végétarien", "Végan", "Sans gluten", "Sans lactose", "Halal", "Healthy / Léger")
        )
    with col2:
        temps_max = st.selectbox(
            "Temps de préparation",
            ("Peu importe", "Express (moins de 15 min)", "Rapide (moins de 30 min)", "Plat mijoté")
        )

    st.subheader("📸 Vos ingrédients (3 photos max)")
    tab_import, tab_camera = st.tabs(("Importer des photos", "Prendre une photo directe"))
    photos_a_analyser = []

    with tab_import:
        uploaded_files = st.file_uploader(
            "Sélectionnez jusqu'à 3 photos (frigo, congélateur, placards)", 
            type=("jpg", "jpeg", "png"), 
            accept_multiple_files=True
        )
        if uploaded_files:
            photos_a_analyser.extend(uploaded_files)

    with tab_camera:
        camera_photo = st.camera_input("Prendre une photo")
        if camera_photo:
            photos_a_analyser.append(camera_photo)

    # Limitation à 3 photos sans utiliser de crochets
    if len(photos_a_analyser) > 3:
        st.warning("⚠️ Maximum 3 photos par analyse. Seules les 3 premières sont gardées.")
        photos_a_analyser = list(photos_a_analyser)
        while len(photos_a_analyser) > 3:
            photos_a_analyser.pop()

    if st.button("✨ Générer ma recette et chercher les promos", type="primary", use_container_width=True):
        if not photos_a_analyser:
            st.warning("Veuillez d'abord ajouter ou prendre au moins une photo.")
        elif not ville:
            st.warning("Veuillez indiquer votre ville pour la recherche de promotions.")
        else:
            try:
                with st.spinner("Analyse de vos placards par Groq Vision..."):
                    content_vision = [
                        {
                            "type": "text",
                            "text": "Liste précisément tous les ingrédients, aliments, épices et produits visibles sur ces photos. Sois exhaustif et concis."
                        }
                    ]
                    for photo in photos_a_analyser:
                        base64_img = encode_image(photo)
                        content_vision.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}
                        })

                    inventaire = None
                    for modele_vision in ("qwen/qwen3.8-27b", "meta-models/muse-spark-open"):
                        try:
                            chat_vision = client.chat.completions.create(
                                model=modele_vision,
                                messages=[{"role": "user", "content": content_vision}],
                                temperature=0.3
                            )
                            premier_choix = next(iter(chat_vision.choices))
                            inventaire = premier_choix.message.content
                            break
                        except Exception as err_vis:
                            dernier_err = err_vis
                            continue

                    if not inventaire:
                        raise dernier_err

                with st.spinner("Création de la recette sur mesure et recherche des promos..."):
                    prompt_recette = f"""
                    Voici l'inventaire des produits disponibles chez l'utilisateur :
                    {inventaire}

                    Contraintes obligatoires à respecter :
                    - Ville de l'utilisateur : {ville}
                    - Régime alimentaire : {regime}
                    - Temps de préparation souhaité : {temps_max}

                    Fais un travail complet structuré exactement ainsi :
                    1. **TITRE DE LA RECETTE** (uniquement le nom du plat sur la première ligne)
                    2. **INGRÉDIENTS DISPONIBLES UTILISÉS**
                    3. **INGRÉDIENTS MANQUANTS** (ajoute 1 à 3 ingrédients essentiels manquants respectant le régime {regime}, ou écris "Aucun").
                    4. **ÉTAPES DE PRÉPARATION** (simples et détaillées).
                    5. **PROMOS AUTOUR DE {ville.upper()}** : Utilise ton outil de recherche web pour trouver les promotions et catalogues en cours cette semaine sur les ingrédients manquants dans les supermarchés (Carrefour, Leclerc, Lidl, Intermarché, Auchan) proches de {ville}. Indique le magasin et l'offre trouvée.
                    6. **IMAGE_PROMPT** : À la toute fin, écris une ligne commençant exactement par "PROMPT_IMG:" suivie d'une courte description en anglais du plat fini pour générer une photo appétissante (ex: PROMPT_IMG: delicious homemade vegetarian pasta with fresh tomatoes, food photography).
                    """

                    chat_recette = client.chat.completions.create(
                        model="openai/gpt-oss-120b",
                        messages=[{"role": "user", "content": prompt_recette}],
                        tools=[{"type": "browser_search"}],
                        temperature=0.5
                    )
                    premier_choix_recette = next(iter(chat_recette.choices))
                    resultat_complet = premier_choix_recette.message.content

                lignes = resultat_complet.split("\n")
                texte_affiche = []
                prompt_image = "delicious homemade gourmet meal, food photography"
                titre_extrait = "Recette du jour"

                for i, ligne in enumerate(lignes):
                    if ligne.strip().startswith("PROMPT_IMG:"):
                        prompt_image = ligne.replace("PROMPT_IMG:", "").strip()
                    else:
                        texte_affiche.append(ligne)
                        if i == 0 and ligne.strip():
                            titre_extrait = ligne.replace("*", "").replace("#", "").strip()

                encoded_prompt = urllib.parse.quote(prompt_image)
                image_url = f"https://pollinations.ai{encoded_prompt}?width=800&height=500&nologo=true"

                st.session_state.derniere_recette = {
                    "titre": titre_extrait,
                    "regime": regime,
                    "image": image_url,
                    "contenu": "\n".join(texte_affiche)
                }

            except Exception as e:
                st.error(f"Détail exact de l'erreur Groq : {e}")

    if st.session_state.derniere_recette:
        recette = st.session_state.derniere_recette
        st.divider()
        st.success("✅ Votre recette et vos promos sont prêtes !")
        
        if st.button("❤️ Sauvegarder cette recette dans mes favoris", use_container_width=True):
            deja_presente = False
            for r in st.session_state.recettes_sauvegardees:
                if r.get("titre") == recette.get("titre"):
                    deja_presente = True
            if not deja_presente:
                st.session_state.recettes_sauvegardees.append(recette)
                st.toast("Recette ajoutée à vos favoris !", icon="❤️")
                st.rerun()
            else:
                st.info("Cette recette est déjà dans vos favoris.")

        st.image(recette.get("image"), caption=recette.get("titre"), use_container_width=True)
        st.markdown(recette.get("contenu"))

# ==========================================
# ONGLET 2 : CARNET DE RECETTES FAVORITES
# ==========================================
with tab_favoris:
    st.subheader("📖 Votre carnet de recettes")
    
    if not st.session_state.recettes_sauvegardees:
        st.info("Vous n'avez pas encore sauvegardé de recette. Générez un plat et cliquez sur le cœur pour le garder ici !")
    else:
        for index, fav in enumerate(st.session_state.recettes_sauvegardees):
            with st.expander(f"🍽️ {fav.get('titre')} ({fav.get('regime')})"):
                st.image(fav.get("image"), use_container_width=True)
                st.markdown(fav.get("contenu"))
                if st.button("🗑️ Supprimer", key=f"del_{index}"):
                    st.session_state.recettes_sauvegardees.pop(index)
                    st.rerun()
