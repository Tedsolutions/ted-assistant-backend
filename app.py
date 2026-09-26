"""
TED Assistant - Backend minimal
--------------------------------
Reçoit les messages du widget de chat, les envoie à Claude,
et gère la sauvegarde des demandes de contact / rendez-vous
quand un visiteur en fait la demande.

Lancer en local :
    pip install -r requirements.txt
    export ANTHROPIC_API_KEY="votre_cle"   (ou mettre dans un fichier .env)
    python app.py
"""

import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic
from database import init_db, save_contact, list_contacts

# --- Configuration ---------------------------------------------------------

app = Flask(__name__)
CORS(app)  # autorise le widget (hébergé sur ton site WordPress) à appeler ce backend

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-5"  # tu peux passer à "claude-haiku-4-5" pour encore moins cher

init_db()

# Prompt système : personnalise ici pour coller à TED Solutions
SYSTEM_PROMPT = """Tu es l'assistant IA de TED Solutions, une entreprise qui aide les TPE et PME
à automatiser leurs tâches et à répondre à leurs clients grâce à l'intelligence artificielle
(chatbots IA, automatisation, solutions sur mesure).

Ton rôle :
- Répondre aux questions des visiteurs sur les services de TED Solutions (chatbots IA,
  automatisation, solutions sur mesure).
- Être chaleureux, clair et concis. Pas de jargon technique inutile.
- Si le visiteur veut être recontacté, obtenir un devis, ou prendre rendez-vous,
  récupère poliment son nom, un moyen de contact (email ou téléphone), et le besoin,
  puis utilise l'outil enregistrer_contact pour le sauvegarder.
- Ne jamais inventer d'informations sur les tarifs précis si tu ne les as pas : oriente
  vers une démo ou un rendez-vous dans ce cas.
"""

# Outil que Claude peut appeler pour enregistrer une demande de contact/RDV
TOOLS = [
    {
        "name": "enregistrer_contact",
        "description": (
            "Enregistre une demande de contact ou de rendez-vous laissée par un visiteur "
            "du site. À utiliser dès que tu as au minimum un nom et un moyen de contact."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nom": {"type": "string", "description": "Nom du visiteur"},
                "email": {"type": "string", "description": "Email du visiteur (si fourni)"},
                "telephone": {"type": "string", "description": "Téléphone du visiteur (si fourni)"},
                "besoin": {"type": "string", "description": "Résumé de sa demande / besoin"},
                "creneau_souhaite": {
                    "type": "string",
                    "description": "Date/créneau souhaité pour un rendez-vous, si mentionné",
                },
            },
            "required": ["nom", "besoin"],
        },
    }
]


def run_tool(tool_name: str, tool_input: dict) -> str:
    """Exécute l'outil demandé par Claude et renvoie un résultat texte."""
    if tool_name == "enregistrer_contact":
        save_contact(
            nom=tool_input.get("nom", ""),
            email=tool_input.get("email", ""),
            telephone=tool_input.get("telephone", ""),
            besoin=tool_input.get("besoin", ""),
            creneau_souhaite=tool_input.get("creneau_souhaite", ""),
        )
        return "Contact enregistré avec succès."
    return "Outil inconnu."


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    user_message = data.get("message", "")
    history = data.get("history", [])  # liste de {role, content} envoyée par le widget

    messages = history + [{"role": "user", "content": user_message}]

    # Boucle d'appel : Claude peut appeler un outil, on lui renvoie le résultat,
    # jusqu'à ce qu'il produise une réponse texte finale.
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            # On ajoute la réponse de l'assistant (contenant l'appel d'outil) à l'historique
            messages.append({ "role": "assistant", "content": [block.model_dump() for block in response.content], })

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result_text = run_tool(block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_text,
                        }
                    )
            messages.append({"role": "user", "content": tool_results})
            continue  # on redemande à Claude sa réponse finale

        # Réponse texte normale
        reply_text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        messages.append({"role": "assistant", "content": reply_text})
        break

    return jsonify({"reply": reply_text, "history": messages})


@app.route("/api/contacts", methods=["GET"])
def get_contacts():
    # ⚠️ v1 sans authentification : à protéger (mot de passe/API key) avant mise en prod
    # si tu comptes accéder à cette route depuis l'extérieur.
    rows = list_contacts()
    contacts = [
        {
            "id": r[0],
            "nom": r[1],
            "email": r[2],
            "telephone": r[3],
            "besoin": r[4],
            "creneau_souhaite": r[5],
            "date_creation": r[6],
        }
        for r in rows
    ]
    return jsonify(contacts)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
